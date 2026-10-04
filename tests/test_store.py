from pathlib import Path

from olivia.store import Store


def test_messages_are_bounded_and_ordered(tmp_path: Path):
    store = Store(tmp_path / "state.sqlite3")
    sid = store.create_session("test")
    for i in range(30):
        store.append_message(sid, "user", f"m{i}")
    rows = store.recent_messages(sid, limit=5)
    assert [r["content"] for r in rows] == ["m25", "m26", "m27", "m28", "m29"]
    assert store.message_count(sid) == 30


def test_memory_supersession_and_recall(tmp_path: Path):
    store = Store(tmp_path / "state.sqlite3")
    store.promote_memory("global", "voice", "neutral Spanish", source="test")
    store.promote_memory("global", "voice", "Argentine Spanish", source="test")
    hits = store.recall_memories("Argentine voice", "global", limit=10)
    assert any(h["value"] == "Argentine Spanish" for h in hits)
    assert all(h["value"] != "neutral Spanish" for h in hits)


def test_store_does_not_keep_legacy_provider_state_table(tmp_path):
    store = Store(tmp_path / "state.sqlite3")
    names = {
        row[0]
        for row in store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "provider_state" not in names
    assert not hasattr(store, "provider_attempt")
    assert not hasattr(store, "provider_success")
    assert not hasattr(store, "provider_failure")
