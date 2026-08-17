from abc import ABC, abstractmethod
from collections.abc import Callable
from html import unescape
import json
import queue
import re
import threading
import time
from urllib import parse, request
from urllib.error import HTTPError, URLError

from app.core.config import Settings
from app.core.errors import UserFacingError


CancelCallback = Callable[[], bool]

LANGUAGE_NAMES = {
    "zh-TW": "Traditional Chinese used in Taiwan. Do not output Simplified Chinese.",
    "en-US": "natural, concise business English",
    "th-TH": "natural, formal business Thai",
}

TRANSLATION_PROFILE_LABELS = {
    "cloud": "雲端模型",
    "local-primary": "地端模型一",
    "local-secondary": "地端模型二",
}


class TranslationService(ABC):
    @abstractmethod
    def translate_slide_text(self, text: str, source_language: str, target_language: str) -> str:
        """Translate concise slide text without adding explanations."""

    @abstractmethod
    def translate_speaker_notes(self, text: str, source_language: str, target_language: str) -> str:
        """Translate speaker notes into natural spoken language."""


class MockTranslationService(TranslationService):
    """Development-only translator. It deliberately does not pretend to translate."""

    def translate_slide_text(self, text: str, source_language: str, target_language: str) -> str:
        return f"[MOCK_TRANSLATION:{target_language}] {text}"

    def translate_speaker_notes(self, text: str, source_language: str, target_language: str) -> str:
        return f"[MOCK_NARRATION_TRANSLATION:{target_language}] {text}"


class OpenAICompatibleTranslationService(TranslationService):
    """Translator for OpenAI-compatible chat-completions APIs."""

    def __init__(
        self,
        settings: Settings,
        *,
        require_api_key: bool = True,
        send_api_key: bool = True,
        default_url: str | None = None,
        cancel_callback: CancelCallback | None = None,
    ) -> None:
        if require_api_key and not settings.translation_api_key:
            raise UserFacingError("translation_not_configured", "尚未設定正式翻譯服務 API 金鑰。")
        self.api_key = settings.translation_api_key if send_api_key else None
        self.api_url = _normalize_chat_completions_url(
            settings.translation_api_url or default_url or "https://api.openai.com/v1/chat/completions"
        )
        self.model = settings.translation_model
        self.cancel_callback = cancel_callback

    def translate_slide_text(self, text: str, source_language: str, target_language: str) -> str:
        return self._translate(text, source_language, target_language, mode="slide")

    def translate_speaker_notes(self, text: str, source_language: str, target_language: str) -> str:
        return self._translate(text, source_language, target_language, mode="notes")

    def _translate(self, text: str, source_language: str, target_language: str, mode: str) -> str:
        def request_once() -> str:
            system_prompt, user_prompt = _build_prompts(text, source_language, target_language, mode)
            payload = {
                "model": self.model,
                "temperature": 0.1,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            http_request = request.Request(
                self.api_url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with request.urlopen(http_request, timeout=180) as response:
                response_body = response.read().decode("utf-8")
            data = json.loads(response_body)
            return data["choices"][0]["message"]["content"].strip()

        try:
            translated = _run_translation_request(request_once, self.cancel_callback, text)
        except HTTPError as exc:
            raise UserFacingError("translation_failed", f"翻譯服務回應錯誤：{_safe_http_error_detail(exc)}") from exc
        except URLError as exc:
            raise UserFacingError("translation_failed", "無法連線到翻譯服務。") from exc
        except TimeoutError as exc:
            raise UserFacingError("translation_failed", "翻譯服務逾時。") from exc
        except UserFacingError:
            raise
        except Exception as exc:
            raise UserFacingError("translation_failed", "翻譯服務回傳格式無法解析。") from exc
        return _require_translated_text(translated)


class OllamaTranslationService(TranslationService):
    """Translator backed by Ollama's native chat API."""

    def __init__(self, settings: Settings, cancel_callback: CancelCallback | None = None) -> None:
        if not settings.translation_api_url:
            raise UserFacingError("translation_not_configured", "尚未設定 Ollama API URL。")
        self.api_url = _normalize_ollama_chat_url(settings.translation_api_url)
        self.model = settings.translation_model
        self.num_gpu = settings.translation_ollama_num_gpu
        self.cancel_callback = cancel_callback

    def translate_slide_text(self, text: str, source_language: str, target_language: str) -> str:
        return self._translate(text, source_language, target_language, mode="slide")

    def translate_speaker_notes(self, text: str, source_language: str, target_language: str) -> str:
        return self._translate(text, source_language, target_language, mode="notes")

    def _translate(self, text: str, source_language: str, target_language: str, mode: str) -> str:
        def request_once() -> str:
            system_prompt, user_prompt = _build_prompts(text, source_language, target_language, mode)
            options: dict[str, float | int] = {"temperature": 0.1}
            if self.num_gpu is not None:
                options["num_gpu"] = self.num_gpu
            payload = {
                "model": self.model,
                "stream": True,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "options": options,
            }
            http_request = request.Request(
                self.api_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            chunks: list[str] = []
            with request.urlopen(http_request, timeout=180) as response:
                while True:
                    _raise_if_cancelled(self.cancel_callback)
                    line = response.readline()
                    if not line:
                        break
                    data = json.loads(line.decode("utf-8"))
                    message = data.get("message") or {}
                    chunks.append(message.get("content", ""))
                    if data.get("done"):
                        break
            streamed = "".join(chunks).strip()
            if streamed:
                return streamed

            payload["stream"] = False
            http_request = request.Request(
                self.api_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(http_request, timeout=180) as response:
                data = json.loads(response.read().decode("utf-8"))
            message = data.get("message") or {}
            return str(message.get("content", "")).strip()

        try:
            translated = _run_translation_request(request_once, self.cancel_callback, text)
        except HTTPError as exc:
            raise UserFacingError("translation_failed", f"Ollama 翻譯服務回應錯誤：{_safe_http_error_detail(exc)}") from exc
        except URLError as exc:
            raise UserFacingError("translation_failed", "無法連線到 Ollama 翻譯服務。") from exc
        except TimeoutError as exc:
            raise UserFacingError("translation_failed", "Ollama 翻譯服務逾時。") from exc
        except UserFacingError:
            raise
        except Exception as exc:
            raise UserFacingError("translation_failed", "Ollama 翻譯服務回傳格式無法解析。") from exc
        return _require_translated_text(translated)


class GeminiTranslationService(TranslationService):
    """Translator backed by the Gemini generateContent REST API."""

    def __init__(self, settings: Settings, cancel_callback: CancelCallback | None = None) -> None:
        if not settings.translation_api_key:
            raise UserFacingError("translation_not_configured", "尚未設定 Gemini API 金鑰。")
        self.api_key = settings.translation_api_key
        self.model = settings.translation_model or "gemini-3-flash-preview"
        self.api_url = settings.translation_api_url or (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )
        self.cancel_callback = cancel_callback

    def translate_slide_text(self, text: str, source_language: str, target_language: str) -> str:
        return self._translate(text, source_language, target_language, mode="slide")

    def translate_speaker_notes(self, text: str, source_language: str, target_language: str) -> str:
        return self._translate(text, source_language, target_language, mode="notes")

    def _translate(self, text: str, source_language: str, target_language: str, mode: str) -> str:
        def request_once() -> str:
            system_prompt, user_prompt = _build_prompts(text, source_language, target_language, mode)
            payload = {
                "contents": [{"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
                "generationConfig": {"temperature": 0.1},
            }
            http_request = request.Request(
                self.api_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "x-goog-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with request.urlopen(http_request, timeout=120) as response:
                response_body = response.read().decode("utf-8")
            data = json.loads(response_body)
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(part.get("text", "") for part in parts).strip()

        try:
            translated = _run_translation_request(request_once, self.cancel_callback, text)
        except HTTPError as exc:
            raise UserFacingError("translation_failed", f"Gemini 翻譯服務回應錯誤：{_safe_http_error_detail(exc)}") from exc
        except URLError as exc:
            raise UserFacingError("translation_failed", "無法連線到 Gemini 翻譯服務。") from exc
        except TimeoutError as exc:
            raise UserFacingError("translation_failed", "Gemini 翻譯服務逾時。") from exc
        except UserFacingError:
            raise
        except Exception as exc:
            raise UserFacingError("translation_failed", "Gemini 翻譯服務回傳格式無法解析。") from exc
        return _require_translated_text(translated)


class GoogleTranslationService(TranslationService):
    """Translator for Google Cloud Translation Basic v2 API keys."""

    def __init__(self, settings: Settings, cancel_callback: CancelCallback | None = None) -> None:
        if not settings.translation_api_key:
            raise UserFacingError("translation_not_configured", "尚未設定 Google 翻譯 API 金鑰。")
        self.api_key = settings.translation_api_key
        self.api_url = settings.translation_api_url or "https://translation.googleapis.com/language/translate/v2"
        self.cancel_callback = cancel_callback

    def translate_slide_text(self, text: str, source_language: str, target_language: str) -> str:
        return self._translate(text, source_language, target_language)

    def translate_speaker_notes(self, text: str, source_language: str, target_language: str) -> str:
        return self._translate(text, source_language, target_language)

    def _translate(self, text: str, source_language: str, target_language: str) -> str:
        def request_once() -> str:
            query = parse.urlencode({"key": self.api_key})
            payload = parse.urlencode(
                {
                    "q": text,
                    "source": source_language,
                    "target": target_language,
                    "format": "text",
                }
            ).encode("utf-8")
            http_request = request.Request(
                f"{self.api_url}?{query}",
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
                method="POST",
            )
            with request.urlopen(http_request, timeout=120) as response:
                response_body = response.read().decode("utf-8")
            data = json.loads(response_body)
            return data["data"]["translations"][0]["translatedText"].strip()

        try:
            translated = _run_translation_request(request_once, self.cancel_callback, text)
        except HTTPError as exc:
            raise UserFacingError("translation_failed", f"Google 翻譯服務回應錯誤：{_safe_http_error_detail(exc)}") from exc
        except URLError as exc:
            raise UserFacingError("translation_failed", "無法連線到 Google 翻譯服務。") from exc
        except TimeoutError as exc:
            raise UserFacingError("translation_failed", "Google 翻譯服務逾時。") from exc
        except UserFacingError:
            raise
        except Exception as exc:
            raise UserFacingError("translation_failed", "Google 翻譯服務回傳格式無法解析。") from exc
        return _require_translated_text(unescape(translated))


def _run_cancellable(operation: Callable[[], str], cancel_callback: CancelCallback | None) -> str:
    _raise_if_cancelled(cancel_callback)
    if cancel_callback is None:
        return operation()

    result_queue: queue.Queue[tuple[bool, str | BaseException]] = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            result_queue.put((True, operation()))
        except BaseException as exc:
            result_queue.put((False, exc))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    while True:
        _raise_if_cancelled(cancel_callback)
        try:
            success, result = result_queue.get(timeout=0.2)
        except queue.Empty:
            continue
        if success:
            return str(result)
        raise result


def _run_translation_request(operation: Callable[[], str], cancel_callback: CancelCallback | None, source_text: str) -> str:
    last_empty = False
    for attempt in range(2):
        try:
            translated = _run_cancellable(operation, cancel_callback).strip()
        except UserFacingError:
            raise
        except Exception:
            _raise_if_cancelled(cancel_callback)
            if attempt == 0:
                time.sleep(1)
                continue
            raise
        if translated:
            return translated
        last_empty = True
        _raise_if_cancelled(cancel_callback)
        if attempt == 0:
            time.sleep(1)

    snippet = re.sub(r"\s+", " ", source_text).strip()[:80]
    if last_empty:
        raise UserFacingError("translation_empty", f"翻譯服務連續兩次回傳空白結果，原文片段：{snippet}")
    raise UserFacingError("translation_failed", "翻譯服務連續兩次回應失敗。")


def _raise_if_cancelled(cancel_callback: CancelCallback | None) -> None:
    if cancel_callback is not None and cancel_callback():
        raise UserFacingError("job_canceled", "翻譯已由使用者停止，未產生可下載檔案。")


def _normalize_chat_completions_url(api_url: str) -> str:
    url = api_url.rstrip("/")
    if url.endswith("/chat/completions"):
        return url
    if url.endswith("/v1"):
        return f"{url}/chat/completions"
    return f"{url}/v1/chat/completions"


def _normalize_ollama_chat_url(api_url: str) -> str:
    url = api_url.rstrip("/")
    if url.endswith("/api/chat"):
        return url
    if url.endswith("/v1"):
        url = url[:-3]
    if url.endswith("/api"):
        return f"{url}/chat"
    return f"{url}/api/chat"


def _build_prompts(text: str, source_language: str, target_language: str, mode: str) -> tuple[str, str]:
    target_name = LANGUAGE_NAMES.get(target_language, target_language)
    if mode == "slide":
        style = (
            "Translate for a corporate presentation slide. Keep it concise. "
            "Do not add explanations, headings, bullets, or new content."
        )
    else:
        style = (
            "Translate speaker notes for natural spoken narration. "
            "Do not summarize, expand, explain, or add content."
        )
    system_prompt = (
        "You are a professional business presentation translator. "
        "Output only the translated text. Preserve numbers, units, URLs, email addresses, "
        "company names, product names, system names, codes, and acronyms. "
        "Do not wrap the answer in quotes or Markdown."
    )
    user_prompt = (
        f"{style}\n"
        f"Source language: {source_language}\n"
        f"Target language: {target_name}\n\n"
        f"Text:\n{text}"
    )
    return system_prompt, user_prompt


def _require_translated_text(translated: str) -> str:
    if not translated:
        raise UserFacingError("translation_failed", "翻譯服務回傳空白結果。")
    return translated


def _safe_http_error_detail(exc: HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace")
        data = json.loads(body)
        message = data.get("error", {}).get("message")
        if message:
            return f"HTTP {exc.code} - {message}"
    except Exception:
        pass
    return f"HTTP {exc.code}"


def resolve_translation_profile(settings: Settings, profile: str | None) -> Settings:
    selected = (profile or "local-primary").lower()
    if selected == "cloud":
        return settings.model_copy(
            update={
                "translation_provider": settings.translation_cloud_provider or "gemini",
                "translation_api_url": settings.translation_cloud_api_url,
                "translation_model": settings.translation_cloud_model or "gemini-3-flash-preview",
            }
        )
    if selected == "local-primary":
        return settings.model_copy(
            update={
                "translation_provider": "ollama",
                "translation_api_url": settings.translation_local_primary_api_url or settings.translation_api_url,
                "translation_model": settings.translation_local_primary_model or settings.translation_model,
            }
        )
    if selected == "local-secondary":
        return settings.model_copy(
            update={
                "translation_provider": "ollama",
                "translation_api_url": settings.translation_local_secondary_api_url,
                "translation_model": settings.translation_local_secondary_model,
            }
        )
    raise UserFacingError("translation_profile_invalid", "翻譯模型選項不支援，請重新選擇。")


def get_translation_options(settings: Settings) -> list[dict[str, str | bool | None]]:
    options = []
    for profile in ("cloud", "local-primary", "local-secondary"):
        resolved = resolve_translation_profile(settings, profile)
        provider = resolved.translation_provider.lower()
        options.append(
            {
                "id": profile,
                "label": TRANSLATION_PROFILE_LABELS[profile],
                "provider": resolved.translation_provider,
                "model": resolved.translation_model,
                "api_url": resolved.translation_api_url if provider == "ollama" else None,
                "available": bool(resolved.translation_model)
                and (provider in {"mock", "ollama"} or bool(resolved.translation_api_key)),
            }
        )
    return options


def get_translation_service(
    settings: Settings,
    profile: str | None = None,
    cancel_callback: CancelCallback | None = None,
) -> TranslationService:
    settings = resolve_translation_profile(settings, profile)
    provider = settings.translation_provider.lower()
    if provider == "ollama":
        return OllamaTranslationService(settings, cancel_callback=cancel_callback)
    if provider == "gemini":
        return GeminiTranslationService(settings, cancel_callback=cancel_callback)
    if provider == "google":
        return GoogleTranslationService(settings, cancel_callback=cancel_callback)
    if provider in {"openai", "external"}:
        return OpenAICompatibleTranslationService(settings, cancel_callback=cancel_callback)
    return MockTranslationService()
