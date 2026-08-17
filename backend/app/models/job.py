from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class JobState(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    canceled = "canceled"
    expired = "expired"


class JobStage(str, Enum):
    validating_upload = "驗證上傳檔案"
    parsing_presentation = "解析簡報"
    extracting_content = "擷取投影片文字與講者備註"
    translating_slide_text = "翻譯投影片文字"
    translating_notes = "翻譯講者備註"
    writing_translation = "將翻譯內容寫回簡報"
    generating_audio = "產生語音"
    embedding_audio = "將語音嵌入投影片"
    validating_output = "驗證輸出簡報"
    completed = "處理完成"
    failed = "處理失敗"


class JobStats(BaseModel):
    processed_text_slides: int = 0
    generated_audio_slides: int = 0
    slides_without_notes: int = 0
    required_audio_slides: list[int] = Field(default_factory=list)


class JobStatus(BaseModel):
    job_id: str
    original_filename: str
    output_filename: str | None = None
    source_language: str
    target_language: str
    translation_profile: str = "local-primary"
    translation_provider: str | None = None
    translation_model: str | None = None
    state: JobState = JobState.pending
    progress_percent: int = 0
    stage: JobStage = JobStage.validating_upload
    current_slide: int = 0
    total_slides: int = 0
    message: str = ""
    created_at: datetime
    completed_at: datetime | None = None
    expires_at: datetime
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    cancel_requested: bool = False
    output_validated: bool = False
    stats: JobStats = Field(default_factory=JobStats)


class JobPaths(BaseModel):
    root: Path
    upload: Path
    working: Path
    audio: Path
    output: Path
    status: Path
