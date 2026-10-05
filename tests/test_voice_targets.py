from olivia.voice.targets import TARGETS


def test_voice_transport_catalog_keeps_direct_wss_default_and_challengers_replaceable():
    assert TARGETS.transport_default == "direct-wss"
    assert TARGETS.transport_challengers == (
        "pipecat-smallwebrtc",
        "livekit-agents",
        "streamcore",
    )
