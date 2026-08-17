from app.utils.filename import make_output_filename, sanitize_filename


def test_output_filename_keeps_readable_name() -> None:
    assert make_output_filename("Training.pptx", "zh-TW") == "Training_zh-TW.pptx"


def test_sanitize_filename_removes_windows_forbidden_chars() -> None:
    assert sanitize_filename("..\\客戶:Training?.pptx") == "客戶Training.pptx"

