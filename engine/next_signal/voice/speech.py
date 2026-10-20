"""Language choice and speech text preparation. Pure functions. Ported from ai-healthcare platform's
app/voice/speech.py; the one change (PLAN.md §5.15 point 6) is removing `resolve_facility`-based ID
replacement entirely, since there is no facility-ID concept in Next Signal. Added Rs/crore/lakh
pronunciation rules since the ported fallback text and report numbers use Indian currency notation that
a TTS voice should say as words, not read digit-by-digit.
"""
import re
import unicodedata

_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")
_HINDI_HINTS = frozenset(
    ["hai", "kya", "kitna", "kitni", "kitne", "kab", "kaise", "mein", "ka", "ki", "ke", "abhi", "haal", "batao", "bataiye"]
)
_WORD_RE = re.compile(r"[a-zA-Z]+")

_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_BRACKETED_RE = re.compile(r"\([^)]*\)|\[[^\]]*\]|\{[^}]*\}")
_BULLET_RE = re.compile(r"^\s*(?:[-•*]|\d+[.)])\s+", re.MULTILINE)
_DASH_RE = re.compile("[" + chr(0x2013) + chr(0x2014) + "]")
_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([.,!?।;:])")

# Indian currency and period notation, spoken as words (PLAN.md §5.15 point 6).
_RS_RE = re.compile(r"\bRs\.?\s*", re.IGNORECASE)
_CRORE_RE = re.compile(r"\bcr\b\.?", re.IGNORECASE)
_PERIOD_RE = re.compile(r"\bQ(\d)\s*FY(\d{2})\b")


def has_devanagari(text: str) -> bool:
    return bool(_DEVANAGARI_RE.search(text))


def detect_text_language(text: str) -> str:
    """Typed text: hi-IN if Devanagari or at least two common Hinglish words."""
    if has_devanagari(text):
        return "hi-IN"
    words = {w.lower() for w in _WORD_RE.findall(text)}
    return "hi-IN" if len(words & _HINDI_HINTS) >= 2 else "en-IN"


def choose_language(pref: str, *, stt_language: str | None = None, text: str = "") -> str:
    """Turn language: the hello preference unless `auto`, then the STT final's language (`en*` gives
    en-IN, anything else hi-IN), then the text heuristic."""
    if pref and pref != "auto":
        return pref
    if stt_language:
        if has_devanagari(text):
            return "hi-IN"  # the STT language tag is low confidence for Hinglish
        return "en-IN" if stt_language.lower().startswith("en") else "hi-IN"
    return detect_text_language(text)


def _speak_numbers(text: str) -> str:
    text = _RS_RE.sub("rupees ", text)
    text = _CRORE_RE.sub("crore", text)
    text = _PERIOD_RE.sub(lambda m: f"Q{m.group(1)} F Y {m.group(2)}", text)
    return text


def prepare_speech(text: str) -> str:
    """Make model text speakable: strip markdown and bracketed content, speak Indian currency and
    period notation as words, collapse whitespace. Never transliterates."""
    text = unicodedata.normalize("NFC", text or "")

    text = _LINK_RE.sub(r"\1", text)
    text = _BRACKETED_RE.sub(" ", text)
    text = _BULLET_RE.sub("", text)
    text = _DASH_RE.sub(", ", text)
    text = _EMOJI_RE.sub("", text)
    text = text.replace("*", "").replace("#", "").replace("`", "").replace("_", " ")
    text = _speak_numbers(text)
    text = re.sub(r"\s+", " ", text).strip()
    text = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    return text.strip()


FALLBACK_TEXT = {
    "en-IN": "Sorry, I could not reach the report data. Please try again.",
    "hi-IN": "माफ़ कीजिए, report data से जुड़ नहीं पाई। कृपया दोबारा कोशिश करें।",
}


def fallback_text(language: str) -> str:
    return FALLBACK_TEXT.get(language, FALLBACK_TEXT["hi-IN"])
