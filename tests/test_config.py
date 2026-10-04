from __future__ import annotations

from pathlib import Path

import pytest

from olivia.config import Settings


def test_reliability_defaults_are_backwards_compatible(tmp_path):
    settings = Settings(data_dir=tmp_path)
    assert settings.circuit_half_open_probes == 1
    assert settings.circuit_jitter_ratio == pytest.approx(0.2)
    assert settings.probe_lease_s == pytest.approx(90.0)
    assert settings.max_provider_attempts == 3
    assert settings.cooldown_rate_limit_s == 60
    assert settings.stream_idle_timeout_s == 0.0
    assert settings.visible_prefix_max_chars == 256
    assert settings.quota_utc_offset_h == 0
    assert settings.hard_zero_cost is True
    # base surface untouched
    assert settings.ttft_timeout_s == 12.0
    assert settings.circuit_base_s == 15
    assert settings.circuit_max_s == 600
    assert settings.db_path == tmp_path / "olivia.sqlite3"


def test_from_env_reads_reliability_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("OLIVIA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("OLIVIA_TTFT_TIMEOUT_S", "0.5")
    monkeypatch.setenv("OLIVIA_CIRCUIT_BASE_S", "3")
    monkeypatch.setenv("OLIVIA_CIRCUIT_MAX_S", "30")
    monkeypatch.setenv("OLIVIA_CIRCUIT_HALF_OPEN_PROBES", "2")
    monkeypatch.setenv("OLIVIA_CIRCUIT_JITTER", "0.1")
    monkeypatch.setenv("OLIVIA_PROBE_LEASE_S", "20")
    monkeypatch.setenv("OLIVIA_MAX_PROVIDER_ATTEMPTS", "5")
    monkeypatch.setenv("OLIVIA_COOLDOWN_RATE_LIMIT_S", "45")
    monkeypatch.setenv("OLIVIA_STREAM_IDLE_TIMEOUT_S", "9")
    monkeypatch.setenv("OLIVIA_VISIBLE_PREFIX_MAX", "64")
    monkeypatch.setenv("OLIVIA_QUOTA_UTC_OFFSET_H", "-3")
    monkeypatch.setenv("OLIVIA_HARD_ZERO_COST", "true")
    monkeypatch.setenv(
        "OLIVIA_PROVIDERS_JSON",
        '[{"name":"groq","base_url":"https://api.groq.com/openai/v1/","model":"m","api_key_env":"GROQ_API_KEY"}]',
    )
    settings = Settings.from_env()
    assert settings.data_dir == tmp_path
    assert settings.ttft_timeout_s == pytest.approx(0.5)
    assert settings.circuit_half_open_probes == 2
    assert settings.circuit_jitter_ratio == pytest.approx(0.1)
    assert settings.probe_lease_s == pytest.approx(20.0)
    assert settings.max_provider_attempts == 5
    assert settings.cooldown_rate_limit_s == 45
    assert settings.stream_idle_timeout_s == pytest.approx(9.0)
    assert settings.visible_prefix_max_chars == 64
    assert settings.quota_utc_offset_h == -3
    assert settings.hard_zero_cost is True
    assert isinstance(settings.data_dir, Path)
    assert settings.providers[0]["name"] == "groq"


def test_from_env_clamps_nonsense_values(monkeypatch, tmp_path):
    monkeypatch.setenv("OLIVIA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("OLIVIA_CIRCUIT_HALF_OPEN_PROBES", "0")
    monkeypatch.setenv("OLIVIA_CIRCUIT_JITTER", "-5")
    monkeypatch.setenv("OLIVIA_MAX_PROVIDER_ATTEMPTS", "999")
    monkeypatch.setenv("OLIVIA_QUOTA_UTC_OFFSET_H", "99")
    monkeypatch.setenv("OLIVIA_TTFT_TIMEOUT_S", "not-a-number")
    monkeypatch.setenv("OLIVIA_PROBE_LEASE_S", "0")
    settings = Settings.from_env()
    assert settings.circuit_half_open_probes == 1
    assert settings.circuit_jitter_ratio == 0.0
    assert settings.max_provider_attempts == 16
    assert settings.quota_utc_offset_h == 14
    assert settings.ttft_timeout_s == 12.0
    assert settings.probe_lease_s == pytest.approx(1.0)


def test_from_env_rejects_non_list_providers(monkeypatch):
    monkeypatch.setenv("OLIVIA_PROVIDERS_JSON", '{"name":"groq"}')
    with pytest.raises(ValueError):
        Settings.from_env()

def test_hard_zero_cost_can_only_be_disabled_explicitly(monkeypatch):
    monkeypatch.setenv("OLIVIA_HARD_ZERO_COST", "0")
    assert Settings.from_env().hard_zero_cost is False
