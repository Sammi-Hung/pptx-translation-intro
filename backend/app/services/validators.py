from pathlib import Path

from app.core.config import Settings
from app.core.errors import UserFacingError

SUPPORTED_LANGUAGES = {"zh-TW", "en-US", "th-TH"}


def validate_languages(source_language: str, target_language: str) -> None:
    if source_language not in SUPPORTED_LANGUAGES or target_language not in SUPPORTED_LANGUAGES:
        raise UserFacingError("unsupported_language", "不支援的語言選項。")
    if source_language == target_language:
        raise UserFacingError("same_language", "原始語言和目標語言不能相同。")


def validate_upload_metadata(filename: str, size: int, settings: Settings) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix != ".pptx":
        raise UserFacingError("unsupported_format", "只支援 .pptx 檔案。")
    if size > settings.max_upload_bytes:
        raise UserFacingError("file_too_large", f"檔案大小不可超過 {settings.max_upload_mb} MB。")

