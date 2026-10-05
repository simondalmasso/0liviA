from pathlib import Path

from olivia.security import contains_secret


ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (
    ROOT / "olivia",
    ROOT / "deploy",
    ROOT / "web",
    ROOT / "cloudflare",
    ROOT / ".github" / "workflows",
)
SKIP = {ROOT / "olivia" / "security.py"}


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
            if contains_secret(text):
                findings.append(str(path.relative_to(ROOT)))
    assert findings == [], f"literal secret-like values found in: {findings}"
