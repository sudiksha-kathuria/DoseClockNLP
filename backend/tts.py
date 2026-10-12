"""
tts.py
------
Generates the spoken reminder using gTTS and caches the mp3 on disk so
the same medicine + language combination is never synthesized twice.

Each supported language has a fixed reminder sentence.
The medicine name is treated as an opaque label - it is only ever
substituted into the sentence, never parsed, split, or acted on. There
is no dosage information anywhere in this module.
"""

import os
import re
import hashlib
import tempfile
from gtts import gTTS

# Languages offered in the form, mapped to gTTS's language codes.
LANGUAGES = [
    ("en", "English"),
    ("hi", "Hindi"),
    ("ta", "Tamil"),
    ("te", "Telugu"),
    ("kn", "Kannada"),
    ("bn", "Bengali"),
]

REMINDER_TEMPLATES = {
    "en": "It's time to take your {name}.",
    "hi": "आपकी {name} दवा लेने का समय हो गया है।",
    "ta": "உங்கள் {name} மருந்தை எடுத்துக்கொள்ள வேண்டிய நேரம் வந்துவிட்டது.",
    "te": "మీ {name} మందు తీసుకునే సమయం వచ్చింది.",
    "kn": "ನಿಮ್ಮ {name} ಔಷಧಿ ತೆಗೆದುಕೊಳ್ಳುವ ಸಮಯವಾಗಿದೆ.",
    "bn": "আপনার {name} ওষুধ খাওয়ার সময় হয়েছে।",
}


def reminder_text(medicine_name, language):
    return REMINDER_TEMPLATES[language].format(name=medicine_name)

# mp3s are cached inside the frontend's static folder so Flask can
# serve them directly at /static/audio/<file>.mp3
AUDIO_DIR = os.path.join(
    os.path.dirname(__file__), "..", "frontend", "static", "audio"
)


def _slugify(text):
    """Turn free-typed medicine names into a safe-ish filename fragment."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug[:40] or "medicine"


def _cache_filename(medicine_name, language):
    """
    Deterministic filename for a given (name, language) pair, so repeat
    reminders reuse the same file instead of re-generating speech.
    A short hash is appended to keep filenames unique even when two
    medicine names slugify to the same thing.
    """
    # Sentence changes invalidate recordings made with the old English template.
    digest = hashlib.sha1(f"{language}|{reminder_text(medicine_name, language)}".encode("utf-8")).hexdigest()[:10]
    return f"{language}_{_slugify(medicine_name)}_{digest}.mp3"


def get_cached_audio(medicine_name, language):
    filename = _cache_filename(medicine_name, language)
    filepath = os.path.join(AUDIO_DIR, filename)
    return f'audio/{filename}' if os.path.isfile(filepath) and os.path.getsize(filepath) > 0 else None


def get_or_create_audio(medicine_name, language):
    """
    Return the audio filename (relative to static/audio/) for this
    reminder, generating + caching it with gTTS if it doesn't exist yet.
    """
    os.makedirs(AUDIO_DIR, exist_ok=True)
    filename = _cache_filename(medicine_name, language)
    filepath = os.path.join(AUDIO_DIR, filename)

    if not get_cached_audio(medicine_name, language):
        sentence = reminder_text(medicine_name, language)
        speech = gTTS(text=sentence, lang=language, timeout=(3, 8))
        fd, temporary = tempfile.mkstemp(dir=AUDIO_DIR, suffix='.mp3')
        os.close(fd)
        try:
            speech.save(temporary)
            os.replace(temporary, filepath)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    return f"audio/{filename}"
