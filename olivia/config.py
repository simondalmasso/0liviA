from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _env_float(name: str, default: float, lo: float, hi: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return min(hi, max(lo, value))


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    value = _env_float(name, float(default), float(lo), float(hi))
    return int(value)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    bind: str = "127.0.0.1"
    port: int = 8080
    ttft_timeout_s: float = 12.0
    circuit_base_s: int = 15
    circuit_max_s: int = 600
    max_history: int = 24
    max_context_chars: int = 48_000
    providers: tuple[dict[str, Any], ...] = ()
    # --- router reliability (impl/deepseek-router-v1) ---
    circuit_half_open_probes: int = 1      # probes allowed while HALF_OPEN
    circuit_jitter_ratio: float = 0.2      # +/- ratio applied to exponential backoff
    probe_lease_s: float = 90.0            # abandoned probes stop wedging HALF_OPEN
    max_provider_attempts: int = 2         # one primary + at most one eligible fallback
    cooldown_rate_limit_s: int = 60        # floor for 429 cooldowns (Retry-After wins)
    stream_idle_timeout_s: float = 0.0     # 0 disables inter-token watchdog
    visible_prefix_max_chars: int = 256    # whitespace-only prefix budget
    quota_utc_offset_h: int = 0            # daily quota day boundary
    hard_zero_cost: bool = True             # fail closed against paid/unverified routes
    build_sha: str = ""                      # exact deployed source commit, when known

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
            port=_env_int("OLIVIA_PORT", 8080, 1, 65535),
            ttft_timeout_s=_env_float("OLIVIA_TTFT_TIMEOUT_S", 12.0, 0.05, 300.0),
            circuit_base_s=_env_int("OLIVIA_CIRCUIT_BASE_S", 15, 1, 3600),
            circuit_max_s=_env_int("OLIVIA_CIRCUIT_MAX_S", 600, 1, 86400),
            max_history=_env_int("OLIVIA_MAX_HISTORY", 24, 1, 200),
            max_context_chars=_env_int("OLIVIA_MAX_CONTEXT_CHARS", 48_000, 16_000, 250_000),
            providers=tuple(parsed),
            circuit_half_open_probes=_env_int("OLIVIA_CIRCUIT_HALF_OPEN_PROBES", 1, 1, 8),
            circuit_jitter_ratio=_env_float("OLIVIA_CIRCUIT_JITTER", 0.2, 0.0, 1.0),
            probe_lease_s=_env_float("OLIVIA_PROBE_LEASE_S", 90.0, 1.0, 3600.0),
            max_provider_attempts=_env_int("OLIVIA_MAX_PROVIDER_ATTEMPTS", 2, 1, 2),
            cooldown_rate_limit_s=_env_int("OLIVIA_COOLDOWN_RATE_LIMIT_S", 60, 1, 86400),
            stream_idle_timeout_s=_env_float("OLIVIA_STREAM_IDLE_TIMEOUT_S", 0.0, 0.0, 600.0),
            visible_prefix_max_chars=_env_int("OLIVIA_VISIBLE_PREFIX_MAX", 256, 1, 65536),
            quota_utc_offset_h=_env_int("OLIVIA_QUOTA_UTC_OFFSET_H", 0, -12, 14),
            hard_zero_cost=True,
            build_sha=os.getenv("OLIVIA_BUILD_SHA", "").strip(),
        )