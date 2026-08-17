from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
import math
import re
import subprocess
import struct
import sys
import tempfile
import wave

from app.core.config import Settings
from app.core.errors import UserFacingError


LANGUAGE_LCIDS = {
    "zh-TW": {"0404"},
    "en-US": {"0409"},
    "th-TH": {"041E"},
}

SAPI_WAV_FORMAT_22KHZ_16BIT_MONO = 22
SAPI_SSFM_CREATE_FOR_WRITE = 3
SAPI_SVS_FLAGS_ASYNC = 1
SAPI_SVSFPURGE_BEFORE_SPEAK = 2
SAPI_SVSF_DEFAULT = 0
MIN_VALID_WAV_BYTES = 1024


@dataclass(frozen=True)
class VoiceAvailability:
    provider: str
    available: bool
    language: str
    voice_name: str | None
    message: str


class TextToSpeechService(ABC):
    file_extension = ".mp3"

    @abstractmethod
    def synthesize(self, text: str, language: str, output_path: Path) -> None:
        """Create one audio file for the provided text and target language."""


class MockTextToSpeechService(TextToSpeechService):
    file_extension = ".wav"

    def synthesize(self, text: str, language: str, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sample_rate = 8000
        duration_seconds = 0.4
        frames = int(sample_rate * duration_seconds)
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            for index in range(frames):
                value = int(500 * math.sin(2 * math.pi * 440 * index / sample_rate))
                wav_file.writeframes(struct.pack("<h", value))


class SapiTextToSpeechService(TextToSpeechService):
    """Local Windows SAPI text-to-speech provider."""

    file_extension = ".wav"

    def synthesize(self, text: str, language: str, output_path: Path) -> None:
        _synthesize_with_sapi_worker(text, language, output_path)


def synthesize_with_sapi_in_process(text: str, language: str, output_path: Path) -> None:
    """Synthesize speech in the current process.

    This is used by the standalone worker process. The web server calls the
    worker instead of running SAPI directly inside FastAPI's background thread.
    """
    _synthesize_with_sapi_com(text, language, output_path)


def _synthesize_with_sapi_worker(text: str, language: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as text_file:
        text_file.write(text)
        text_path = Path(text_file.name)
    try:
        command = [
            sys.executable,
            "-m",
            "app.services.sapi_worker",
            "--language",
            language,
            "--text-file",
            str(text_path),
            "--output",
            str(output_path),
        ]
        output_path.unlink(missing_ok=True)
        result = subprocess.run(
            command,
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
            timeout=300,
            creationflags=_sapi_worker_creation_flags(),
        )
    except subprocess.TimeoutExpired as exc:
        raise UserFacingError("tts_failed", "Windows SAPI 語音產生逾時。") from exc
    finally:
        try:
            text_path.unlink(missing_ok=True)
        except Exception:
            pass

    if result.returncode != 0:
        detail = _sanitize_sapi_worker_error(result.stderr or result.stdout or "")
        if detail:
            raise UserFacingError("tts_failed", f"Windows SAPI 語音產生失敗：{detail}")
        raise UserFacingError("tts_failed", "Windows SAPI 語音產生失敗，請確認備註內容與目標語言語音包。")

    if not _is_valid_audio_file(output_path):
        raise UserFacingError("tts_failed", "Windows SAPI 未產生有效語音檔，請確認備註內容與目標語言語音包。")


def _synthesize_with_sapi_com(text: str, language: str, output_path: Path) -> None:
        cleaned_text = _clean_tts_text(text)
        if not cleaned_text:
            raise UserFacingError("tts_failed", "講者備註沒有可朗讀內容，無法產生語音。")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import pythoncom
            import win32com.client
        except Exception as exc:
            raise UserFacingError("tts_unavailable", "此電腦無法使用 Windows SAPI 語音服務。") from exc

        stream = None
        voice = None
        voice_token = None
        audio_format = None
        try:
            pythoncom.CoInitialize()
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            voice_token = _select_sapi_voice(voice.GetVoices(), language)
            if voice_token is None:
                raise UserFacingError("tts_voice_missing", _missing_voice_message(language))

            audio_format = win32com.client.Dispatch("SAPI.SpAudioFormat")
            audio_format.Type = SAPI_WAV_FORMAT_22KHZ_16BIT_MONO
            stream = win32com.client.Dispatch("SAPI.SpFileStream")
            stream.Format = audio_format
            stream.Open(str(output_path.resolve()), SAPI_SSFM_CREATE_FOR_WRITE, False)

            voice.Voice = voice_token
            voice.AudioOutputStream = stream
            for chunk in _chunk_tts_text(cleaned_text):
                voice.Speak(chunk, SAPI_SVSF_DEFAULT)
            voice.AudioOutputStream = None
            stream.Close()
            stream = None
        except UserFacingError:
            raise
        except Exception as exc:
            raise UserFacingError("tts_failed", "Windows SAPI 語音產生失敗，請確認備註內容與目標語言語音包。") from exc
        finally:
            if voice is not None:
                try:
                    voice.AudioOutputStream = None
                except Exception:
                    pass
            if stream is not None:
                try:
                    stream.Close()
                except Exception:
                    pass
            voice = None
            voice_token = None
            stream = None
            audio_format = None
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


class ExternalTextToSpeechService(TextToSpeechService):
    def __init__(self, settings: Settings) -> None:
        if not settings.tts_api_key or not settings.tts_api_url:
            raise UserFacingError("tts_not_configured", "正式語音服務尚未設定。")
        self.settings = settings

    def synthesize(self, text: str, language: str, output_path: Path) -> None:
        raise UserFacingError("tts_failed", "正式語音服務介面尚未實作，請在 app/services/tts.py 串接公司 API。")


def _clean_tts_text(text: str) -> str:
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    cleaned = cleaned.replace("\u200b", "").replace("\ufeff", "")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _chunk_tts_text(text: str, max_chars: int = 1800) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current = ""
    for part in re.split(r"(?<=[。！？.!?])\s+", text):
        if not part:
            continue
        if len(current) + len(part) + 1 <= max_chars:
            current = f"{current} {part}".strip()
            continue
        if current:
            chunks.append(current)
        while len(part) > max_chars:
            chunks.append(part[:max_chars])
            part = part[max_chars:]
        current = part
    if current:
        chunks.append(current)
    return chunks


def _is_valid_audio_file(path: Path) -> bool:
    try:
        return path.exists() and path.stat().st_size >= MIN_VALID_WAV_BYTES
    except Exception:
        return False


def _sanitize_sapi_worker_error(detail: str) -> str:
    lines = []
    for line in detail.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if "Win32 exception occurred releasing IUnknown" in cleaned:
            continue
        lines.append(cleaned)
    return " ".join(lines).strip()[:180]


def _sapi_worker_creation_flags() -> int:
    if sys.platform != "win32":
        return 0
    return getattr(subprocess, "CREATE_NEW_CONSOLE", 0)


def _select_sapi_voice(voices, language: str):
    expected_lcids = LANGUAGE_LCIDS.get(language, set())
    if not expected_lcids:
        return None

    for index in range(voices.Count):
        token = voices.Item(index)
        raw_languages = str(token.GetAttribute("Language") or "")
        token_lcids = {_normalize_lcid(value) for value in raw_languages.split(";") if value.strip()}
        if token_lcids & expected_lcids:
            return token
    return None


def _find_sapi_voice_name(language: str) -> str | None:
    try:
        import pythoncom
        import win32com.client
    except Exception:
        return None

    try:
        pythoncom.CoInitialize()
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        voice_token = _select_sapi_voice(voice.GetVoices(), language)
        if voice_token is None:
            return None
        try:
            return str(voice_token.GetDescription())
        except Exception:
            return "Windows SAPI voice"
    except Exception:
        return None
    finally:
        voice = None
        voice_token = None
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def _normalize_lcid(value: str) -> str:
    return value.strip().upper().zfill(4)


def _missing_voice_message(language: str) -> str:
    labels = {
        "zh-TW": "繁體中文",
        "en-US": "英文",
        "th-TH": "泰文",
    }
    label = labels.get(language, language)
    return (
        f"此電腦未安裝可用的 {label} Windows 語音包，無法產生講者備註旁白。"
        "請到 Windows 設定 > 時間與語言 > 語音，安裝對應語言的語音套件後再重試。"
    )


def get_voice_availability(settings: Settings, language: str) -> VoiceAvailability:
    provider = settings.tts_provider.lower()
    if provider != "sapi":
        return VoiceAvailability(
            provider=provider,
            available=True,
            language=language,
            voice_name=None,
            message="目前未使用 Windows SAPI 語音服務。",
        )

    voice_name = _find_sapi_voice_name(language)
    if voice_name is None:
        return VoiceAvailability(
            provider=provider,
            available=False,
            language=language,
            voice_name=None,
            message=_missing_voice_message(language),
        )
    return VoiceAvailability(
        provider=provider,
        available=True,
        language=language,
        voice_name=voice_name,
        message="已偵測到對應的 Windows 語音包。",
    )


def get_tts_service(settings: Settings) -> TextToSpeechService:
    provider = settings.tts_provider.lower()
    if provider == "sapi":
        return SapiTextToSpeechService()
    if provider == "external":
        return ExternalTextToSpeechService(settings)
    return MockTextToSpeechService()
