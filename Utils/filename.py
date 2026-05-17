import re
import unicodedata

_INVALID_FS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_COLLAPSE_WS = re.compile(r"\s+")
MAX_STEM_LEN = 80


def sanitize_filename_stem(value: str, fallback: str) -> str:
    text = (value or "").strip()
    if not text:
        text = fallback
    text = unicodedata.normalize("NFC", text)
    text = _INVALID_FS_CHARS.sub("", text)
    text = _COLLAPSE_WS.sub(" ", text).strip(" .")
    if not text:
        text = fallback
    if len(text) > MAX_STEM_LEN:
        text = text[:MAX_STEM_LEN].rstrip(" .")
    return text or fallback
