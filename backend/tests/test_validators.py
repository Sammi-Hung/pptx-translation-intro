from app.core.config import Settings
from app.core.errors import UserFacingError
from app.services.validators import validate_languages, validate_upload_metadata


def test_valid_pptx_upload_is_accepted() -> None:
    settings = Settings(max_upload_mb=50)
    validate_upload_metadata("training.pptx", 1024, settings)


def test_wrong_extension_is_rejected() -> None:
    settings = Settings(max_upload_mb=50)
    try:
        validate_upload_metadata("training.pdf", 1024, settings)
    except UserFacingError as exc:
        assert exc.code == "unsupported_format"
    else:
        raise AssertionError("Expected unsupported_format")


def test_large_file_is_rejected() -> None:
    settings = Settings(max_upload_mb=50)
    try:
        validate_upload_metadata("training.pptx", 51 * 1024 * 1024, settings)
    except UserFacingError as exc:
        assert exc.code == "file_too_large"
    else:
        raise AssertionError("Expected file_too_large")


def test_same_language_is_rejected() -> None:
    try:
        validate_languages("zh-TW", "zh-TW")
    except UserFacingError as exc:
        assert exc.code == "same_language"
    else:
        raise AssertionError("Expected same_language")

