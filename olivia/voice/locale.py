from __future__ import annotations

from dataclasses import dataclass

ES_AR = "es-AR"
DEFAULT_LOCALE = ES_AR


@dataclass(frozen=True)
class VoiceProfile:
    locale: str = DEFAULT_LOCALE
    voice_id: str | None = None
    speaking_rate: float = 1.0

    def validate(self) -> None:
        if normalize_locale(self.locale) != "es-ar":
            raise ValueError("0liviA default voice profile must be es-AR")
        if not 0.75 <= self.speaking_rate <= 1.35:
            raise ValueError("speaking_rate outside safe range")


@dataclass(frozen=True)
class VoiceCandidate:
    name: str
    engine: str
    locales: tuple[str, ...]
    streaming: bool
    local: bool
    license_note: str = ""


@dataclass(frozen=True)
class LocalePolicy:
    locale: str = ES_AR
    require_exact_voice_locale: bool = True

    def voice_accepted(self, candidate: VoiceCandidate) -> bool:
        wanted = normalize_locale(self.locale)
        if self.require_exact_voice_locale:
            return any(normalize_locale(item) == wanted for item in candidate.locales)
        language = wanted.split("-", 1)[0]
        return any(normalize_locale(item).split("-", 1)[0] == language for item in candidate.locales)


def normalize_locale(locale: str) -> str:
    return locale.strip().lower().replace("_", "-")


def is_argentine_spanish(locale: str) -> bool:
    return normalize_locale(locale) == "es-ar"


# Candidate capability labels only. Generic Spanish support is deliberately not
# upgraded to exact es-AR acceptance without a measured/verified voice.
VOICE_TARGETS: tuple[VoiceCandidate, ...] = (
    VoiceCandidate("Pocket TTS candidate", "pocket-tts", ("es",), True, True),
    VoiceCandidate("Piper fallback", "piper", ("es",), True, True),
    VoiceCandidate("Kokoro challenger", "kokoro", ("es",), True, True),
)
