import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (
    ROOT / "olivia",
    ROOT / "deploy",
    ROOT / "web",
    ROOT / "cloudflare",
    ROOT / ".github" / "workflows",
)
SKIP = {ROOT / "olivia" / "security.py"}

# Deliberately stricter than runtime DLP: scan only credential shapes that can
# be literal secrets in source, not ordinary variables named "password".
LITERAL_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.I),
    re.compile(r"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"""Bearer\s+["']?[A-Za-z0-9._~+/=-]{24,}["']?""", re.I),
)


def test_runtime_and_deploy_sources_contain_no_literal_secrets():
    findings = []
    for base in SCAN_ROOTS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path in SKIP:
                continue
            if path.suffix not in {".py", ".sh", ".html", ".js", ".mjs", ".yml", ".yaml", ".toml", ".service", ".example"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(pattern.search(text) for pattern in LITERAL_SECRET_PATTERNS):
                findings.append(str(path.relative_to(ROOT)))
    assert findings == [], f"literal secret-like values found in: {findings}"
