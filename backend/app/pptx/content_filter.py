import re

URL_RE = re.compile(r"^(https?://|www\.)\S+$", re.IGNORECASE)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
READABLE_RE = re.compile(r"[\w\u0E00-\u0E7F\u4E00-\u9FFF]", re.UNICODE)


def should_translate_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.isnumeric():
        return False
    if URL_RE.match(stripped) or EMAIL_RE.match(stripped):
        return False
    if not READABLE_RE.search(stripped):
        return False
    if all(not char.isalpha() for char in stripped):
        return False
    return True


def has_speakable_text(text: str) -> bool:
    return should_translate_text(text)

