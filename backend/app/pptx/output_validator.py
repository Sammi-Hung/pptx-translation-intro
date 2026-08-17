from pathlib import Path

from pptx import Presentation

from app.core.errors import UserFacingError


def count_media_shapes(path: Path) -> int:
    prs = Presentation(str(path))
    count = 0
    for slide in prs.slides:
        for shape in slide.shapes:
            if getattr(shape, "name", "").startswith("TranslatedNarration_"):
                count += 1
    return count


def count_shapes(path: Path) -> int:
    prs = Presentation(str(path))
    return sum(len(slide.shapes) for slide in prs.slides)


def validate_output(
    original_path: Path,
    output_path: Path,
    expected_slide_count: int,
    required_audio_slides: list[int],
    audio_embedded: bool,
) -> None:
    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise UserFacingError("output_validation_failed", "輸出簡報不存在或檔案大小為零。")
    try:
        original = Presentation(str(original_path))
        output = Presentation(str(output_path))
    except Exception as exc:
        raise UserFacingError("output_validation_failed", "輸出簡報無法重新開啟。") from exc
    if len(output.slides) != expected_slide_count or len(output.slides) != len(original.slides):
        raise UserFacingError("output_validation_failed", "輸出簡報的投影片數量不正確。")
    if count_shapes(output_path) < count_shapes(original_path):
        raise UserFacingError("output_validation_failed", "輸出簡報可能遺失原有圖片或圖形。")
    if required_audio_slides:
        if not audio_embedded:
            raise UserFacingError("output_validation_failed", "需要語音的頁面未完成音訊嵌入。")
        embedded_count = count_media_shapes(output_path)
        if embedded_count < len(required_audio_slides):
            raise UserFacingError("output_validation_failed", "輸出簡報缺少部分翻譯旁白音訊。")
