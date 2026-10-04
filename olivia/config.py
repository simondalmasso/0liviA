from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    bind: str = "127.0.0.1"
    port: int = 8080
    ttft_timeout_s: float = 12.0
    circuit_base_s: int = 15
    circuit_max_s: int = 600
    max_history: int = 24
    providers: tuple[dict[str, Any], ...] = ()

    @property
    def db_path(self) -> Path:
        return self.data_dir / "olivia.sqlite3"

    @classmethod
    def from_env(cls) -> "Settings":
        default_data = Path.home() / ".local" / "share" / "0livia"
        raw = os.getenv("OLIVIA_PROVIDERS_JSON", "[]")
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            raise ValueError("OLIVIA_PROVIDERS_JSON must be a JSON array")
        return cls(
            data_dir=Path(os.getenv("OLIVIA_DATA_DIR", default_data)).expanduser(),
            bind=os.getenv("OLIVIA_BIND", "127.0.0.1"),
            port=int(os.getenv("OLIVIA_PORT", "8080")),
            ttft_timeout_s=float(os.getenv("OLIVIA_TTFT_TIMEOUT_S", "12")),
            circuit_base_s=int(os.getenv("OLIVIA_CIRCUIT_BASE_S", "15")),
            circuit_max_s=int(os.getenv("OLIVIA_CIRCUIT_MAX_S", "600")),
            max_history=int(os.getenv("OLIVIA_MAX_HISTORY", "24")),
            providers=tuple(parsed),
        )
