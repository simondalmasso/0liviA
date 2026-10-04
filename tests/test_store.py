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


def test_workspace_projects_sessions_and_library_are_durable(tmp_path: Path):
    path = tmp_path / "workspace.sqlite3"
    store = Store(path)
    projects = store.list_projects()
    assert len(projects) == 1
    default_project = projects[0]
    assert default_project["name"] == "0liviA"

    pid = store.create_project("Producto")
    sid = store.create_session("Arquitectura", project_id=pid)
    item_id = store.create_library_item("Spec", "Contrato durable")

    sessions = store.list_sessions(limit=20)
    assert any(row["id"] == sid and row["project_id"] == pid for row in sessions)
    library = store.list_library_items()
    assert any(row["id"] == item_id and row["title"] == "Spec" for row in library)

    store.close()
    reopened = Store(path)
    assert any(row["id"] == pid and row["name"] == "Producto" for row in reopened.list_projects())
    assert any(row["id"] == sid and row["project_id"] == pid for row in reopened.list_sessions())
    assert any(row["id"] == item_id and row["value"] == "Contrato durable" for row in reopened.list_library_items())


def test_existing_sessions_are_migrated_into_default_project(tmp_path: Path):
    path = tmp_path / "legacy.sqlite3"
    import sqlite3
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, updated_at REAL NOT NULL)"
    )
    conn.execute(
        "INSERT INTO sessions(id,title,created_at,updated_at) VALUES('legacy','Viejo',1,1)"
    )
    conn.commit()
    conn.close()

    store = Store(path)
    row = next(item for item in store.list_sessions() if item["id"] == "legacy")
    assert row["project_id"]
    assert store.project_exists(row["project_id"])
