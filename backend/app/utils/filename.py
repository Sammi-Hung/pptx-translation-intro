import re
from pathlib import Path

WINDOWS_FORBIDDEN = r'<>:"/\|?*'


def sanitize_filename(filename: str, fallback: str = "presentation.pptx") -> str:
    """Return a Windows-safe filename while preserving readable Unicode text."""
    name = Path(filename).name.strip()
    name = "".join(ch for ch in name if ch >= " " and ch not in WINDOWS_FORBIDDEN)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name:
        return fallback
    return name[:180]


def make_output_filename(original_filename: str, target_language: str) -> str:
    safe = sanitize_filename(original_filename)
    stem = Path(safe).stem or "presentation"
    return f"{stem}_{target_language}.pptx"

