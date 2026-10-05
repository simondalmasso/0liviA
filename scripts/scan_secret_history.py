from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", re.IGNORECASE),
    "github_token": re.compile(r"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{20,}\b"),
    "github_fine_grained_pat": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    "openai_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}

git = shutil.which("git")
if not git:
    raise SystemExit("git executable not found")

proc = subprocess.run(
    [
        git, "log", "--all", "-p", "--no-color",
        "--", "olivia", "deploy", "web", "cloudflare", ".github/workflows",
    ],
    cwd=ROOT,
    text=True,
    capture_output=True,
    check=True,
)
history = proc.stdout

hits = [name for name, pattern in PATTERNS.items() if pattern.search(history)]
if hits:
    raise SystemExit(
        "high-confidence secret pattern detected in Git history: "
        + ", ".join(sorted(hits))
        + ". Rotate/revoke at the provider before rewriting history."
    )
print("git history secret scan: clean")
