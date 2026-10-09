import time

import pytest

from olivia.world_intel import FEEDS, WorldIntel, _source_link, format_brief


def test_fixed_official_sources_and_unsafe_citations_are_replaced():
    assert FEEDS["usgs"].startswith("https://earthquake.usgs.gov/")
    assert FEEDS["eonet"].startswith("https://eonet.gsfc.nasa.gov/")
    assert _source_link("https://attacker.example/steal", "earthquake.usgs.gov", FEEDS["usgs"]) == FEEDS["usgs"]
    assert _source_link("http://earthquake.usgs.gov/a", "earthquake.usgs.gov", FEEDS["usgs"]) == FEEDS["usgs"]


def test_source_attribution_sanitized_labels_and_data_gaps():
    text = format_brief({
        "usgs": ({"features": [
            {"properties": {"mag": 5.37, "place": "Test\nEarthquake", "url": "https://earthquake.usgs.gov/earthquakes/eventpage/abc"}},
        ]}, False),
        "eonet": (None, False),
    })
    assert "M5.4 · Test Earthquake" in text
    assert "Fuente [USGS]:" in text
    assert "NASA EONET: sin respuesta verificable" in text
    assert "no significa ausencia de eventos" in text
    assert "https://earthquake.usgs.gov/earthquakes/eventpage/abc" in text


class StubIntel(WorldIntel):
    def __init__(self):
        super().__init__()
        self.calls = []

    async def _load(self, key):
        self.calls.append(key)
        if key == "usgs":
            return {"features": []}
        return {"events": []}


@pytest.mark.asyncio
async def test_on_demand_cache_prevents_repeated_network_calls():
    intel = StubIntel()
    first = await intel.brief()
    second = await intel.brief()
    assert first.splitlines()[0].startswith("Inteligencia pública")
    assert "El feed consultado no informó eventos" in second
    assert intel.calls == ["usgs", "eonet"]


@pytest.mark.asyncio
async def test_stale_cache_is_explicit_and_upstream_failure_is_not_quiet():
    intel = StubIntel()
    intel._cache["usgs"] = (time.monotonic() - 601, {"features": []})
    async def failed(key):
        raise ValueError("offline")
    intel._load = failed
    value, stale = await intel._get("usgs")
    assert value == {"features": []}
    assert stale is True
    text = await intel.brief()
    assert "USGS: caché vencida" in text
    assert "NASA EONET: sin respuesta verificable" in text
