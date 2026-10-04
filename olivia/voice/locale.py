from __future__ import annotations

from dataclasses import dataclass


DEFAULT_LOCALE = "es-AR"


@dataclass(frozen=True, slots=True)
class VoiceProfile:
    locale: str = DEFAULT_LOCALE
    voice_id: str | None = None
    speaking_rate: float = 1.0

    def validate(self) -> None:
        if self.locale != DEFAULT_LOCALE:
            raise ValueError("0liviA default voice profile must be es-AR")
        if not 0.75 <= self.speaking_rate <= 1.35:
            raise ValueError("speaking_rate outside safe range")


def is_argentine_spanish(locale: str) -> bool:
    return locale.strip().lower().replace("_", "-") == "es-ar"
