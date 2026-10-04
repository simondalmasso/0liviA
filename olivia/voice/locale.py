from __future__ import annotations

from dataclasses import dataclass

ES_AR = "es-AR"


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
        if self.require_exact_voice_locale:
            return self.locale in candidate.locales
        language = self.locale.split("-", 1)[0].lower()
        return any(item.lower().split("-", 1)[0] == language for item in candidate.locales)


VOICE_TARGETS: tuple[VoiceCandidate, ...] = (
    VoiceCandidate("Pocket TTS candidate", "pocket-tts", (ES_AR, "es"), True, True),
    VoiceCandidate("Piper fallback", "piper", ("es",), True, True),
    VoiceCandidate("Kokoro challenger", "kokoro", ("es",), True, True),
)
