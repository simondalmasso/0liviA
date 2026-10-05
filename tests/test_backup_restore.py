import os
import sqlite3
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKUP = ROOT / "deploy" / "backup.sh"
RESTORE = ROOT / "deploy" / "restore.sh"


def run(script: Path, *args: str, env: dict[str, str]):
    return subprocess.run(
        ["bash", str(script), *args],
        cwd=ROOT,
        env={**os.environ, **env},
        text=True,
        capture_output=True,
        check=False,
    )


def test_encrypted_backup_and_restore_round_trip(tmp_path: Path):
    source = tmp_path / "source.sqlite3"
    restored = tmp_path / "restored.sqlite3"
    encrypted = tmp_path / "backup.sqlite3.enc"
    secret_value = "durable private payload"

    conn = sqlite3.connect(source)
    conn.execute("CREATE TABLE demo(value TEXT NOT NULL)")
    conn.execute("INSERT INTO demo(value) VALUES(?)", (secret_value,))
    conn.commit()
    conn.close()

    env = {
        "OLIVIA_DB_PATH": str(source),
        "OLIVIA_BACKUP_DIR": str(tmp_path),
        "OLIVIA_BACKUP_PASSPHRASE": "test-passphrase-0123456789",
    }
    backed = run(BACKUP, str(encrypted), env=env)
    assert backed.returncode == 0, backed.stderr
    assert encrypted.exists()
    assert (Path(str(encrypted) + ".sha256")).exists()
    assert secret_value.encode() not in encrypted.read_bytes()

    restored_run = run(
        RESTORE,
        str(encrypted),
        env={**env, "OLIVIA_RESTORE_TARGET": str(restored)},
    )
    assert restored_run.returncode == 0, restored_run.stderr

    conn = sqlite3.connect(restored)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT value FROM demo").fetchone()[0] == secret_value
    finally:
        conn.close()


def test_restore_fails_with_wrong_passphrase(tmp_path: Path):
    source = tmp_path / "source.sqlite3"
    encrypted = tmp_path / "backup.sqlite3.enc"
    conn = sqlite3.connect(source)
    conn.execute("CREATE TABLE demo(value TEXT)")
    conn.commit()
    conn.close()

    good = {
        "OLIVIA_DB_PATH": str(source),
        "OLIVIA_BACKUP_PASSPHRASE": "correct-passphrase-0123456789",
    }
    assert run(BACKUP, str(encrypted), env=good).returncode == 0
    bad = {
        "OLIVIA_BACKUP_PASSPHRASE": "wrong-passphrase-01234567890",
        "OLIVIA_RESTORE_TARGET": str(tmp_path / "bad.sqlite3"),
    }
    result = run(RESTORE, str(encrypted), env=bad)
    assert result.returncode != 0
    assert not Path(bad["OLIVIA_RESTORE_TARGET"]).exists()
