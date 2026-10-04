from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_product_docs_do_not_claim_stale_build_state():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs" / "IMPLEMENTATION_PLAN.md").read_text(encoding="utf-8")

    assert "next implementation slice" not in readme
    assert "45 passed" not in plan
    assert "MiniMax — voice contracts" not in plan
    assert "olivia/voice/" in readme
    assert "Temporary production bridge" in (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")


def test_repository_has_one_canonical_super_order_and_archives_old_council_prompt():
    assert (ROOT / "SUPER_ORDER_END_TO_END.md").is_file()
    assert not (ROOT / "docs" / "SUPER_ORDER.md").exists()
    assert not (ROOT / "docs" / "COUNCIL_HANDOFF.md").exists()
    assert (ROOT / "docs" / "history" / "COUNCIL_HANDOFF.md").is_file()
    assert (ROOT / "docs" / "history" / "SUPER_ORDER_LEGACY.md").is_file()


def test_browser_cache_is_explicitly_non_durable():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "browser storage may be used only as a disposable bridge cache" in agents
    assert "never the durable source of truth" in agents


def test_deploy_has_one_canonical_bootstrap():
    assert (ROOT / "deploy" / "bootstrap-a1.sh").is_file()
    assert not (ROOT / "deploy" / "install.sh").exists()
    deploy_readme = (ROOT / "deploy" / "README.md").read_text(encoding="utf-8")
    assert "./deploy/bootstrap-a1.sh" in deploy_readme
    assert "./deploy/install.sh" not in deploy_readme


def test_production_bootstrap_requires_immutable_ref_and_hides_gateway_token():
    bootstrap = (ROOT / "deploy" / "bootstrap-a1.sh").read_text(encoding="utf-8")
    cloud_init = (ROOT / "deploy" / "cloud-init-a1.yaml").read_text(encoding="utf-8")

    assert 'ALLOW_MUTABLE_REF="${ALLOW_MUTABLE_REF:-0}"' in bootstrap
    assert '[[ "$REF" =~ ^[0-9a-fA-F]{40}$ ]]' in bootstrap
    assert 'ALLOW_MUTABLE_REF' in bootstrap
    assert 'OLIVIA_OWNER_PASSWORD_VERIFIER=${OWNER_VERIFIER}' in bootstrap
    assert 'OWNER_PASSWORD=${OWNER_PASSWORD}' in bootstrap
    assert 'TOKEN=${TOKEN}' not in bootstrap.split('cat > "${STATE_ROOT}/bootstrap-info" <<EOF', 1)[1]
    assert 'chmod 0600 "${STATE_ROOT}/bootstrap-info"' in bootstrap

    assert 'REF="${REF:-}"' in cloud_init
    assert '^[0-9a-fA-F]{40}$' in cloud_init


def test_env_examples_document_owner_cookie_auth_without_plaintext_password():
    for path in (ROOT / ".env.example", ROOT / "deploy" / "olivia.env.example"):
        content = path.read_text(encoding="utf-8")
        assert "OLIVIA_OWNER_PASSWORD_VERIFIER=" in content
        assert "OLIVIA_OWNER_PASSWORD=" not in content
