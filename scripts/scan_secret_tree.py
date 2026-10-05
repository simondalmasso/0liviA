from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from olivia.security import contains_secret


ROOT = Path(__file__).resolve().parents[1]
SURFACES = (
    "olivia",
    "deploy",
    "web",
    "cloudflare",
    ".github/workflows",
)


def tracked_runtime_files() -> list[Path]:
    git = shutil.which("git")
    if not git:
        raise SystemExit("git executable not found")
    proc = subprocess.run(
        [git, "ls-files", "-z", "--", *SURFACES],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    out: list[Path] = []
    for raw in proc.stdout.split(b"\0"):
        if not raw:
            continue
        out.append(ROOT / raw.decode("utf-8", errors="strict"))
    return out


hits: list[str] = []
for path in tracked_runtime_files():
    try:
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data[:8192]:
            continue
        text = data.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        continue
    if contains_secret(text):
        hits.append(str(path.relative_to(ROOT)))

if hits:
    raise SystemExit(
        "high-confidence secret pattern detected in tracked runtime tree: "
        + ", ".join(sorted(hits))
    )

print("tracked runtime tree secret scan: clean")
