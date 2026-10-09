import sqlite3

import pytest

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




def test_owner_registration_is_single_and_durable(tmp_path: Path):
    path = tmp_path / "owner-account.sqlite3"
    store = Store(path)

    assert store.get_owner_account() is None
    assert store.register_owner("Owner@Example.com", "scrypt$demo") is True
    account = store.get_owner_account()
    assert account["email"] == "owner@example.com"
    assert account["password_verifier"] == "scrypt$demo"
    assert store.register_owner("other@example.com", "scrypt$other") is False

    store.close()
    reopened = Store(path)
    account = reopened.get_owner_account()
    assert account["email"] == "owner@example.com"


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


def test_security_event_retention_prunes_old_and_bounds_count(tmp_path: Path):
    store = Store(tmp_path / "security-retention.sqlite3")
    with store._lock:
        for i in range(12):
            store._conn.execute(
                "INSERT INTO events(session_id,job_id,type,payload_json,created_at) VALUES(NULL,NULL,?,?,?)",
                ("security.login_failed", "{}", float(i)),
            )
        store._conn.execute(
            "INSERT INTO events(session_id,job_id,type,payload_json,created_at) VALUES(NULL,NULL,?,?,?)",
            ("demo.keep", "{}", 1.0),
        )

    removed = store.prune_security_events(now=100.0, retention_s=95.0, keep_latest=5)
    rows = store.recent_events(prefix="security.", limit=100)
    assert removed >= 7
    assert len(rows) <= 5
    assert all(row["created_at"] >= 5.0 for row in rows)
    assert store.recent_events(prefix="demo.", limit=10)


def test_store_database_file_is_owner_only(tmp_path: Path):
    path = tmp_path / "private.sqlite3"
    store = Store(path)
    try:
        assert path.stat().st_mode & 0o777 == 0o600
    finally:
        store.close()


def test_store_sets_schema_version(tmp_path: Path):
    path = tmp_path / "versioned.sqlite3"
    store = Store(path)
    store.close()

    conn = sqlite3.connect(path)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    finally:
        conn.close()


def test_store_rejects_future_schema_version(tmp_path: Path):
    path = tmp_path / "future.sqlite3"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA user_version=999")
    conn.execute("CREATE TABLE future_only(value TEXT)")
    conn.commit()
    conn.close()

    with pytest.raises(ValueError, match="newer schema"):
        Store(path)

    conn = sqlite3.connect(path)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 999
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='future_only'"
        ).fetchone() == ("future_only",)
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='projects'"
        ).fetchone() is None
    finally:
        conn.close()


def test_legacy_session_migration_enforces_project_reference(tmp_path: Path):
    path = tmp_path / "legacy-fk.sqlite3"
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
    try:
        with pytest.raises(sqlite3.IntegrityError):
            store._conn.execute(
                "INSERT INTO sessions(id,title,project_id,created_at,updated_at) VALUES(?,?,?,?,?)",
                ("orphan", "Huérfana", "missing-project", 2, 2),
            )
        with pytest.raises(sqlite3.IntegrityError):
            store._conn.execute(
                "UPDATE sessions SET project_id=? WHERE id='legacy'",
                ("missing-project",),
            )
        default_project = next(
            row["project_id"] for row in store.list_sessions() if row["id"] == "legacy"
        )
        with pytest.raises(sqlite3.IntegrityError):
            store._conn.execute(
                "DELETE FROM projects WHERE id=?",
                (default_project,),
            )
    finally:
        store.close()


def test_trusted_device_last_seen_touch_is_bounded(tmp_path: Path):
    store = Store(tmp_path / "device-touch.sqlite3")
    device_id = store.create_trusted_device("Mobile", expires_at=2_000_000_000)

    with store._lock:
        store._conn.execute(
            "UPDATE trusted_devices SET last_seen_at=? WHERE id=?",
            (1_900_000_000.0, device_id),
        )

    assert store.trusted_device_active(device_id, now=1_900_000_100) is True
    with store._lock:
        first = store._conn.execute(
            "SELECT last_seen_at FROM trusted_devices WHERE id=?",
            (device_id,),
        ).fetchone()["last_seen_at"]
    assert first == 1_900_000_000.0

    assert store.trusted_device_active(device_id, now=1_900_000_301) is True
    with store._lock:
        second = store._conn.execute(
            "SELECT last_seen_at FROM trusted_devices WHERE id=?",
            (device_id,),
        ).fetchone()["last_seen_at"]
    assert second == 1_900_000_301.0


def test_job_lease_single_owner_and_no_implicit_replay(tmp_path: Path):
    path = tmp_path / "leased.sqlite3"
    owner_a = Store(path)
    owner_b = Store(path)
    job_id = owner_a.create_job("code")
    token = owner_a.claim_queued_job(job_id, lease_seconds=120, now=100)
    assert isinstance(token, str) and len(token) == 32
    assert owner_b.claim_queued_job(job_id, now=101) is None
    assert owner_b.renew_job_lease(job_id, "wrong-owner", now=101) is False
    assert owner_b.checkpoint_leased_job(job_id, "wrong-owner", {"bad": True}, now=101) is False
    with pytest.raises(PermissionError, match="leased"):
        owner_b.checkpoint_job(job_id, "complete", {"bad": True})
    assert "lease_token" not in owner_b.get_job(job_id)
    assert owner_a.renew_job_lease(job_id, token, lease_seconds=120, now=110) is True
    assert owner_a.checkpoint_leased_job(job_id, token, {"step": 1}, now=115) is True
    # An expired running lease cannot be silently stolen and replayed.
    assert owner_a.renew_job_lease(job_id, token, now=231) is False
    assert owner_b.claim_queued_job(job_id, now=232) is None
    assert owner_a.finish_leased_job(job_id, token, "complete", {}, now=231) is False
    assert owner_a.get_job(job_id)["status"] == "running"
    # An operator must resolve the uncertain outcome; never re-dispatch here.
    owner_a.close()
    owner_b.close()


def test_job_lease_terminal_receipt_and_secret_redaction(tmp_path: Path):
    store = Store(tmp_path / "job-receipt.sqlite3")
    job_id = store.create_job("browser")
    secret = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
    token = store.claim_queued_job(job_id, now=10, lease_seconds=200)
    assert token is not None
    assert store.checkpoint_leased_job(job_id, token, {"note": f"secret {secret}"}, now=20)
    assert store.finish_leased_job(job_id, "invalid", "complete", {}, now=25) is False
    with pytest.raises(ValueError):
        store.finish_leased_job(job_id, token, "dispatched", {}, now=25)
    assert store.finish_leased_job(job_id, token, "complete", {"result": f"redacted {secret}"}, now=30)
    assert store.finish_leased_job(job_id, token, "failed", {}, now=31) is False
    result = store.get_job(job_id)
    assert result["status"] == "complete"
    assert "lease_token" not in result
    assert "lease_expires_at" in result and result["lease_expires_at"] is None
    assert secret not in str(result)
    assert "[REDACTED_SECRET]" in str(result)
    store.close()


def test_job_leases_migrate_existing_schema_without_discarding_legacy_jobs(tmp_path: Path):
    path = tmp_path / "old-jobs.sqlite3"
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE jobs (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
            repo TEXT, worktree TEXT, checkpoint_json TEXT NOT NULL DEFAULT '{}',
            created_at REAL NOT NULL, updated_at REAL NOT NULL
        )"""
    )
    conn.execute(
        "INSERT INTO jobs(id,kind,status,checkpoint_json,created_at,updated_at) VALUES(?,?,?,?,?,?)",
        ("legacy-job", "code", "queued", '{"legacy": true}', 1, 1)
    )
    conn.commit()
    conn.close()
    store = Store(path)
    assert store.get_job("legacy-job")["checkpoint"]["legacy"] is True
    token = store.claim_queued_job("legacy-job", now=100)
    assert token is not None
    store.close()
    reopened = Store(path)
    assert reopened.get_job("legacy-job")["status"] == "running"
    assert reopened.finish_leased_job("legacy-job", token, "failed", {"reason": "manual"}, now=120)
    reopened.close()


def test_job_claim_is_atomic_across_connections(tmp_path: Path):
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "job-race.sqlite3"
    stores = [Store(path) for _ in range(6)]
    job_id = stores[0].create_job("code")
    try:
        with ThreadPoolExecutor(max_workers=len(stores)) as executor:
            claims = list(executor.map(lambda s: s.claim_queued_job(job_id), stores))
        assert sum(value is not None for value in claims) == 1
        assert stores[0].get_job(job_id)["status"] == "running"
    finally:
        for store in stores:
            store.close()


def test_job_lease_duration_fails_closed(tmp_path: Path):
    store = Store(tmp_path / "invalid-lease.sqlite3")
    job_id = store.create_job("code")
    for invalid in (0, -1, 3601):
        with pytest.raises(ValueError, match="lease_seconds"):
            store.claim_queued_job(job_id, lease_seconds=invalid)
        with pytest.raises(ValueError, match="lease_seconds"):
            store.renew_job_lease(job_id, "token", lease_seconds=invalid)
    assert store.get_job(job_id)["status"] == "queued"
    store.close()


def test_lease_handoff_requires_owner_and_unexpired_clock(tmp_path):
    store = Store(tmp_path / "handoff.sqlite3")
    job_id = store.create_job("code")
    token = store.claim_queued_job(job_id, lease_seconds=100, now=10)
    assert token is not None
    assert store.handoff_leased_job(job_id, "wrong", {"bad": True}, now=20) is False
    assert store.handoff_leased_job(job_id, token, {"accepted": True}, now=111) is False
    assert store.handoff_leased_job(job_id, token, {"accepted": True}, now=25) is True
    assert store.handoff_leased_job(job_id, token, {"accepted": True}, now=26) is False
    job = store.get_job(job_id)
    assert job["status"] == "dispatched"
    assert job["checkpoint"]["accepted"] is True
    assert job["lease_expires_at"] is None
    assert "lease_token" not in job
    assert store.claim_queued_job(job_id) is None
    store.close()
