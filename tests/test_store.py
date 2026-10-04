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


def test_store_redacts_secrets_at_durable_boundary(tmp_path: Path):
    store = Store(tmp_path / "dlp-boundary.sqlite3")
    secret = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"

    project_id = store.create_project(f"Proyecto {secret}")
    session_id = store.create_session(f"Sesión {secret}", project_id=project_id)
    store.append_message(session_id, "user", f"mensaje {secret}")
    store.create_library_item("Clave", f"valor {secret}")
    store.promote_memory("global", "token", f"memoria {secret}", source="test")
    job_id = store.create_job("code")
    store.checkpoint_job(job_id, "failed", {"error": f"falló con {secret}"})
    store.record_event("demo", {"detail": f"evento {secret}"}, session_id=session_id)

    rendered = repr({
        "projects": store.list_projects(),
        "sessions": store.list_sessions(),
        "messages": store.recent_messages(session_id),
        "library": store.list_library_items(),
        "memories": store.list_memories(),
        "job": store.get_job(job_id),
    })
    assert secret not in rendered
    assert "[REDACTED_SECRET]" in rendered

    with store._lock:
        event_payloads = [
            row["payload_json"]
            for row in store._conn.execute("SELECT payload_json FROM events").fetchall()
        ]
    assert secret not in repr(event_payloads)


def test_trusted_devices_are_durable_touchable_and_revocable(tmp_path: Path):
    path = tmp_path / "devices.sqlite3"
    store = Store(path)
    device_id = store.create_trusted_device("Chrome · Windows", expires_at=2_000_000_000)

    devices = store.list_trusted_devices(now=1_900_000_000)
    assert any(row["id"] == device_id and row["label"] == "Chrome · Windows" for row in devices)
    assert store.trusted_device_active(device_id, now=1_900_000_001) is True

    store.close()
    reopened = Store(path)
    assert reopened.trusted_device_active(device_id, now=1_900_000_002) is True
    assert reopened.delete_trusted_device(device_id) == 1
    assert reopened.trusted_device_active(device_id, now=1_900_000_003) is False


def test_expired_trusted_devices_are_pruned(tmp_path: Path):
    store = Store(tmp_path / "expired-devices.sqlite3")
    device_id = store.create_trusted_device("Viejo", expires_at=100)
    assert store.trusted_device_active(device_id, now=101) is False
    assert store.list_trusted_devices(now=101) == []
