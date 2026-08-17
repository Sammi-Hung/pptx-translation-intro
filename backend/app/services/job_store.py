import json
import shutil
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.config import Settings
from app.models.job import JobPaths, JobStage, JobState, JobStatus
from app.utils.filename import make_output_filename


class JobStore:
    """File-backed job status store with a process-local single-job lock."""

    _active_lock = threading.Lock()
    _active_job_id: str | None = None

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = settings.storage_root
        self.root.mkdir(parents=True, exist_ok=True)

    def acquire_slot(self, job_id: str) -> bool:
        with JobStore._active_lock:
            if JobStore._active_job_id is not None:
                return False
            JobStore._active_job_id = job_id
            return True

    def release_slot(self, job_id: str) -> None:
        with JobStore._active_lock:
            if JobStore._active_job_id == job_id:
                JobStore._active_job_id = None

    def create_job(
        self,
        original_filename: str,
        source_language: str,
        target_language: str,
        translation_profile: str = "local-primary",
        translation_provider: str | None = None,
        translation_model: str | None = None,
    ) -> JobStatus:
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=self.settings.retention_minutes)
        paths = self.paths(job_id)
        paths.root.mkdir(parents=True, exist_ok=False)
        paths.audio.mkdir(parents=True, exist_ok=True)
        status = JobStatus(
            job_id=job_id,
            original_filename=original_filename,
            output_filename=make_output_filename(original_filename, target_language),
            source_language=source_language,
            target_language=target_language,
            translation_profile=translation_profile,
            translation_provider=translation_provider,
            translation_model=translation_model,
            created_at=now,
            expires_at=expires,
            message="已建立工作",
        )
        self.save(status)
        return status

    def paths(self, job_id: str) -> JobPaths:
        root = self.root / job_id
        return JobPaths(
            root=root,
            upload=root / "upload.pptx",
            working=root / "working.pptx",
            audio=root / "audio",
            output=root / "output.pptx",
            status=root / "status.json",
        )

    def get(self, job_id: str) -> JobStatus | None:
        status_path = self.paths(job_id).status
        if not status_path.exists():
            return None
        return JobStatus.model_validate_json(status_path.read_text(encoding="utf-8"))

    def save(self, status: JobStatus) -> None:
        paths = self.paths(status.job_id)
        paths.root.mkdir(parents=True, exist_ok=True)
        paths.status.write_text(
            json.dumps(status.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def update(
        self,
        job_id: str,
        *,
        state: JobState | None = None,
        stage: JobStage | None = None,
        progress_percent: int | None = None,
        current_slide: int | None = None,
        total_slides: int | None = None,
        message: str | None = None,
    ) -> JobStatus:
        status = self.get_required(job_id)
        if state is not None:
            status.state = state
        if stage is not None:
            status.stage = stage
        if progress_percent is not None:
            status.progress_percent = max(0, min(100, progress_percent))
        if current_slide is not None:
            status.current_slide = current_slide
        if total_slides is not None:
            status.total_slides = total_slides
        if message is not None:
            status.message = message
        self.save(status)
        return status

    def fail(self, job_id: str, code: str, message: str) -> JobStatus:
        status = self.get_required(job_id)
        status.state = JobState.failed
        status.stage = JobStage.failed
        status.progress_percent = max(status.progress_percent, 1)
        status.completed_at = datetime.now(timezone.utc)
        status.expires_at = status.completed_at + timedelta(minutes=self.settings.retention_minutes)
        status.error_code = code
        status.error_message = message
        status.message = message
        self.save(status)
        return status

    def request_cancel(self, job_id: str) -> JobStatus:
        status = self.get_required(job_id)
        if status.state not in {JobState.pending, JobState.running}:
            return status
        status.cancel_requested = True
        status.message = "正在停止翻譯，請稍候。"
        self.save(status)
        return status

    def cancel(self, job_id: str, message: str = "翻譯已停止。") -> JobStatus:
        status = self.get_required(job_id)
        now = datetime.now(timezone.utc)
        status.state = JobState.canceled
        status.stage = JobStage.failed
        status.completed_at = now
        status.expires_at = now + timedelta(minutes=self.settings.retention_minutes)
        status.error_code = "job_canceled"
        status.error_message = message
        status.message = message
        status.output_validated = False
        self.save(status)
        return status

    def complete(self, job_id: str) -> JobStatus:
        status = self.get_required(job_id)
        now = datetime.now(timezone.utc)
        status.state = JobState.completed
        status.stage = JobStage.completed
        status.progress_percent = 100
        status.completed_at = now
        status.expires_at = now + timedelta(minutes=self.settings.retention_minutes)
        status.message = "處理完成"
        self.save(status)
        return status

    def get_required(self, job_id: str) -> JobStatus:
        status = self.get(job_id)
        if status is None:
            raise KeyError(job_id)
        return status

    def cleanup_expired(self) -> int:
        now = datetime.now(timezone.utc)
        removed = 0
        for child in self.root.iterdir():
            if not child.is_dir():
                continue
            status_path = child / "status.json"
            if not status_path.exists():
                continue
            try:
                status = JobStatus.model_validate_json(status_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if status.expires_at <= now and status.state not in {JobState.pending, JobState.running}:
                shutil.rmtree(child, ignore_errors=True)
                removed += 1
        return removed
