from dataclasses import dataclass, field
from pathlib import Path
import shutil

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.util import Pt

from app.core.errors import UserFacingError
from app.pptx.content_filter import has_speakable_text, should_translate_text
from app.services.translation import TranslationService

ALLOWED_PLACEHOLDERS = {
    PP_PLACEHOLDER.TITLE,
    PP_PLACEHOLDER.CENTER_TITLE,
    PP_PLACEHOLDER.SUBTITLE,
    PP_PLACEHOLDER.BODY,
    PP_PLACEHOLDER.OBJECT,
}
EXCLUDED_PLACEHOLDERS = {
    PP_PLACEHOLDER.DATE,
    PP_PLACEHOLDER.FOOTER,
    PP_PLACEHOLDER.SLIDE_NUMBER,
}
EXCLUDED_NAME_KEYWORDS = {
    "footer",
    "date",
    "slide number",
    "頁尾",
    "日期",
    "頁碼",
}


@dataclass
class ParagraphTarget:
    slide_number: int
    shape_index: int
    shape_name: str
    paragraph_index: int
    text: str


@dataclass
class SlideNote:
    slide_number: int
    text: str
    translated_text: str | None = None


@dataclass
class PresentationContent:
    total_slides: int
    paragraph_targets: list[ParagraphTarget] = field(default_factory=list)
    notes: list[SlideNote] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def load_presentation(path: Path) -> Presentation:
    try:
        return Presentation(str(path))
    except Exception as exc:
        raise UserFacingError("corrupt_pptx", "PowerPoint 檔案可能已損壞或無法讀取。") from exc


def is_supported_text_shape(shape) -> bool:
    """Return True for slide shapes whose text is in scope for translation."""
    shape_type = getattr(shape, "shape_type", None)
    if shape_type == MSO_SHAPE_TYPE.GROUP:
        return False
    if getattr(shape, "has_table", False) or getattr(shape, "has_chart", False):
        return False
    if not getattr(shape, "has_text_frame", False):
        return False

    shape_name = str(getattr(shape, "name", "")).lower()
    if any(keyword in shape_name for keyword in EXCLUDED_NAME_KEYWORDS):
        return False

    if shape.is_placeholder:
        placeholder_type = shape.placeholder_format.type
        if placeholder_type in EXCLUDED_PLACEHOLDERS:
            return False
        return placeholder_type in ALLOWED_PLACEHOLDERS

    # Many editable PowerPoint text objects are AutoShapes with a text frame,
    # not MSO_SHAPE_TYPE.TEXT_BOX. Include them unless explicitly excluded.
    return True


def paragraph_text(paragraph) -> str:
    if paragraph.runs:
        return "".join(run.text for run in paragraph.runs).strip()
    return (paragraph.text or "").strip()


def extract_presentation_content(path: Path) -> PresentationContent:
    prs = load_presentation(path)
    content = PresentationContent(total_slides=len(prs.slides))
    for slide_index, slide in enumerate(prs.slides, start=1):
        for shape_index, shape in enumerate(slide.shapes):
            if not is_supported_text_shape(shape):
                continue
            for paragraph_index, paragraph in enumerate(shape.text_frame.paragraphs):
                text = paragraph_text(paragraph)
                if should_translate_text(text):
                    content.paragraph_targets.append(
                        ParagraphTarget(
                            slide_number=slide_index,
                            shape_index=shape_index,
                            shape_name=shape.name,
                            paragraph_index=paragraph_index,
                            text=text,
                        )
                    )
        note_text = read_speaker_notes(slide)
        if note_text is not None and has_speakable_text(note_text):
            content.notes.append(SlideNote(slide_number=slide_index, text=note_text))
    return content


def read_speaker_notes(slide) -> str | None:
    if not slide.has_notes_slide:
        return None
    text_frame = slide.notes_slide.notes_text_frame
    if text_frame is None:
        return None
    paragraphs = []
    for paragraph in text_frame.paragraphs:
        text = paragraph_text(paragraph)
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs).strip() or None


def write_speaker_notes(slide, text: str) -> None:
    text_frame = slide.notes_slide.notes_text_frame
    text_frame.clear()
    lines = text.splitlines() or [text]
    text_frame.paragraphs[0].text = lines[0]
    for line in lines[1:]:
        paragraph = text_frame.add_paragraph()
        paragraph.text = line


def translate_and_write_presentation(
    input_path: Path,
    output_path: Path,
    source_language: str,
    target_language: str,
    translator: TranslationService,
    progress_callback,
    cancel_callback=lambda: False,
) -> PresentationContent:
    """Translate eligible slide text and notes, preserving paragraph/run formatting where possible."""
    shutil.copy2(input_path, output_path)
    content = extract_presentation_content(output_path)
    prs = load_presentation(output_path)
    translated_text_slides: set[int] = set()

    targets_by_slide_shape: dict[tuple[int, int, int], ParagraphTarget] = {
        (target.slide_number, target.shape_index, target.paragraph_index): target
        for target in content.paragraph_targets
    }

    total_targets = max(1, len(content.paragraph_targets))
    completed_targets = 0
    for slide_index, slide in enumerate(prs.slides, start=1):
        for shape_index, shape in enumerate(slide.shapes):
            if not is_supported_text_shape(shape):
                continue
            for paragraph_index, paragraph in enumerate(shape.text_frame.paragraphs):
                _raise_if_cancelled(cancel_callback)
                target = targets_by_slide_shape.get((slide_index, shape_index, paragraph_index))
                if target is None:
                    continue
                try:
                    translated = translator.translate_slide_text(target.text, source_language, target_language)
                except UserFacingError:
                    raise
                except Exception as exc:
                    raise UserFacingError("slide_translation_failed", f"第 {slide_index} 頁文字翻譯失敗。") from exc
                _raise_if_cancelled(cancel_callback)
                write_translated_paragraph(paragraph, translated)
                shrink_runs_if_needed(paragraph, target.text, translated, content, slide_index, shape.name)
                translated_text_slides.add(slide_index)
                completed_targets += 1
                progress_callback(slide_index, completed_targets, total_targets)

    for note in content.notes:
        _raise_if_cancelled(cancel_callback)
        try:
            note.translated_text = translator.translate_speaker_notes(note.text, source_language, target_language)
        except UserFacingError:
            raise
        except Exception as exc:
            raise UserFacingError("notes_translation_failed", f"第 {note.slide_number} 頁講者備註翻譯失敗。") from exc
        _raise_if_cancelled(cancel_callback)
        write_speaker_notes(prs.slides[note.slide_number - 1], note.translated_text)

    content.stats_processed_text_slides = len(translated_text_slides)  # type: ignore[attr-defined]
    prs.save(str(output_path))
    return content


def _raise_if_cancelled(cancel_callback) -> None:
    if cancel_callback():
        raise UserFacingError("job_canceled", "翻譯已由使用者停止，未產生可下載檔案。")


def write_translated_paragraph(paragraph, translated: str) -> None:
    if paragraph.runs:
        paragraph.runs[0].text = translated
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.text = translated


def shrink_runs_if_needed(
    paragraph,
    original: str,
    translated: str,
    content: PresentationContent,
    slide: int,
    shape_name: str,
) -> None:
    if len(translated) <= max(24, int(len(original) * 1.35)):
        return
    for run in paragraph.runs[:1]:
        size = run.font.size.pt if run.font.size is not None else 18
        while size > 14 and len(translated) > max(24, int(len(original) * 1.35)):
            size -= 1
            run.font.size = Pt(size)
            if size <= 14:
                break
        if size <= 14:
            content.warnings.append(f"第 {slide} 頁「{shape_name}」翻譯後可能超出文字方塊，已降至 14 pt。")
