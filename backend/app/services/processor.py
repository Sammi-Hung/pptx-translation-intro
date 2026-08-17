import logging
from pathlib import Path

from app.core.config import Settings
from app.core.errors import UserFacingError
from app.models.job import JobStage, JobState
from app.pptx.audio_embedder import AudioEmbedder
from app.pptx.output_validator import validate_output
from app.pptx.processor import extract_presentation_content, translate_and_write_presentation
from app.services.job_store import JobStore
from app.services.translation import get_translation_service
from app.services.tts import get_tts_service, get_voice_availability

logger = logging.getLogger(__name__)


class PresentationJobProcessor:
    def __init__(self, settings: Settings, store: JobStore) -> None:
        self.settings = settings
        self.store = store

    def run(self, job_id: str) -> None:
        if not self.store.acquire_slot(job_id):
            self.store.fail(job_id, "busy", "目前已有一份簡報正在處理，請稍後再試。")
            return
        try:
            self._run(job_id)
        except UserFacingError as exc:
            if exc.code == "job_canceled":
                self.store.cancel(job_id, exc.message)
                return
            logger.exception("Job %s failed with user-facing error %s", job_id, exc.code)
            self.store.fail(job_id, exc.code, exc.message)
        except Exception:
            logger.exception("Job %s failed unexpectedly", job_id)
            self.store.fail(job_id, "unexpected_error", "處理失敗，請確認檔案格式後再試。")
        finally:
            self.store.release_slot(job_id)

    def _run(self, job_id: str) -> None:
        status = self.store.get_required(job_id)
        paths = self.store.paths(job_id)
        translator = get_translation_service(
            self.settings,
            status.translation_profile,
            cancel_callback=lambda: self.store.get_required(job_id).cancel_requested,
        )
        tts = get_tts_service(self.settings)
        embedder = AudioEmbedder(self.settings)
        self._raise_if_cancelled(job_id)

        voice_status = get_voice_availability(self.settings, status.target_language)
        if not voice_status.available:
            raise UserFacingError("tts_voice_missing", voice_status.message)

        self.store.update(
            job_id,
            state=JobState.running,
            stage=JobStage.parsing_presentation,
            progress_percent=5,
            message="正在解析簡報",
        )
        content = extract_presentation_content(paths.upload)
        self._raise_if_cancelled(job_id)
        status.total_slides = content.total_slides
        status.stats.slides_without_notes = content.total_slides - len({note.slide_number for note in content.notes})
        status.stats.required_audio_slides = [note.slide_number for note in content.notes]
        if (status.translation_provider or self.settings.translation_provider).lower() == "mock":
            status.warnings.append("目前使用模擬翻譯模式，輸出不是正式翻譯結果。")
        if self.settings.tts_provider.lower() == "sapi":
            status.warnings.append("目前使用 Windows 本機語音 SAPI；語音品質與可用語言取決於此電腦安裝的語音包。")
        self.store.save(status)

        self.store.update(
            job_id,
            stage=JobStage.extracting_content,
            progress_percent=10,
            total_slides=content.total_slides,
            message="正在擷取投影片文字與講者備註",
        )

        def on_text_progress(slide_number: int, completed: int, total: int) -> None:
            self._raise_if_cancelled(job_id)
            percent = 12 + int((completed / total) * 38)
            self.store.update(
                job_id,
                stage=JobStage.translating_slide_text,
                progress_percent=min(percent, 50),
                current_slide=slide_number,
                message=f"正在翻譯第 {slide_number}/{content.total_slides} 頁文字",
            )

        translated_path = paths.working
        translated_content = translate_and_write_presentation(
            paths.upload,
            translated_path,
            status.source_language,
            status.target_language,
            translator,
            on_text_progress,
            lambda: self.store.get_required(job_id).cancel_requested,
        )
        self._raise_if_cancelled(job_id)

        status = self.store.get_required(job_id)
        status.warnings.extend(translated_content.warnings)
        status.stats.processed_text_slides = getattr(translated_content, "stats_processed_text_slides", 0)
        self.store.save(status)

        self.store.update(job_id, stage=JobStage.translating_notes, progress_percent=50, message="正在翻譯講者備註")
        audio_files: dict[int, Path] = {}
        notes_total = max(1, len(translated_content.notes))
        for index, note in enumerate(translated_content.notes, start=1):
            self._raise_if_cancelled(job_id)
            self.store.update(
                job_id,
                stage=JobStage.generating_audio,
                progress_percent=50 + int((index - 1) / notes_total * 40),
                current_slide=note.slide_number,
                message=f"正在產生第 {note.slide_number} 頁講者備註語音",
            )
            output_audio = paths.audio / f"slide_{note.slide_number:03d}{tts.file_extension}"
            self._synthesize_slide_audio_with_retry(
                tts,
                note.translated_text or note.text,
                status.target_language,
                output_audio,
                note.slide_number,
                job_id,
            )
            self._raise_if_cancelled(job_id)
            audio_files[note.slide_number] = output_audio
            self.store.update(
                job_id,
                stage=JobStage.generating_audio,
                progress_percent=50 + int(index / notes_total * 40),
                current_slide=note.slide_number,
                message=f"已完成第 {note.slide_number} 頁講者備註語音",
            )

        status = self.store.get_required(job_id)
        status.stats.generated_audio_slides = len(audio_files)
        self.store.save(status)

        self.store.update(job_id, stage=JobStage.embedding_audio, progress_percent=92, message="正在將語音嵌入投影片")
        self._raise_if_cancelled(job_id)
        embedder.embed(translated_path, audio_files, paths.output)
        audio_embedded = True

        self.store.update(job_id, stage=JobStage.validating_output, progress_percent=97, message="正在驗證輸出簡報")
        self._raise_if_cancelled(job_id)
        validate_output(paths.upload, paths.output, content.total_slides, list(audio_files.keys()), audio_embedded)
        status = self.store.get_required(job_id)
        status.output_validated = True
        self.store.save(status)
        self.store.complete(job_id)

    def _raise_if_cancelled(self, job_id: str) -> None:
        if self.store.get_required(job_id).cancel_requested:
            raise UserFacingError("job_canceled", "翻譯已由使用者停止，未產生可下載檔案。")

    def _synthesize_slide_audio_with_retry(
        self,
        tts,
        text: str,
        language: str,
        output_audio: Path,
        slide_number: int,
        job_id: str,
    ) -> None:
        last_error: UserFacingError | None = None
        for attempt in range(2):
            try:
                output_audio.unlink(missing_ok=True)
                tts.synthesize(text, language, output_audio)
                if output_audio.exists() and output_audio.stat().st_size > 0:
                    return
                last_error = UserFacingError("tts_failed", "Windows SAPI 未產生有效語音檔。")
            except UserFacingError as exc:
                last_error = exc
            except Exception as exc:
                last_error = UserFacingError("tts_failed", "語音產生程序發生錯誤。")

            self._raise_if_cancelled(job_id)
            output_audio.unlink(missing_ok=True)
            if attempt == 0:
                continue

        if last_error is not None:
            raise UserFacingError(last_error.code, f"第 {slide_number} 頁語音產生失敗：{last_error.message}") from last_error
        raise UserFacingError("tts_failed", f"第 {slide_number} 頁語音產生失敗。")
