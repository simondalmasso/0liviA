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
    assert 'OLIVIA_OWNER_PASSWORD_VERIFIER=${OWNER_VERIFIER}' not in bootstrap
    assert 'OWNER_PASSWORD=${OWNER_PASSWORD}' not in bootstrap
    assert 'REGISTRATION=first-run' in bootstrap
    assert 'TOKEN=${TOKEN}' not in bootstrap.split('cat > "${STATE_ROOT}/bootstrap-info" <<EOF', 1)[1]
    assert 'chmod 0600 "${STATE_ROOT}/bootstrap-info"' in bootstrap

    assert 'REF="${REF:-}"' in cloud_init
    assert '^[0-9a-fA-F]{40}$' in cloud_init


def test_env_examples_document_first_run_registration_without_plaintext_password():
    for path in (ROOT / ".env.example", ROOT / "deploy" / "olivia.env.example"):
        content = path.read_text(encoding="utf-8")
        assert "OLIVIA_REGISTRATION_TOKEN=" in content
        assert "OLIVIA_OWNER_PASSWORD_VERIFIER=" not in content
        assert "OLIVIA_OWNER_PASSWORD=" not in content


def test_bootstrap_verifies_llama_and_model_sha256_before_use():
    bootstrap = (ROOT / "deploy" / "bootstrap-a1.sh").read_text(encoding="utf-8")
    assert "llama_sha256=" in bootstrap
    assert "MODEL_SHA256=" in bootstrap
    assert bootstrap.count("sha256sum -c -") >= 2
    assert "9f454c895ab49d4173cfb3995a39e4f8fe21b364787db8e1ca2778ee7f39aa36" in bootstrap
    assert "43bfc230e612d20efd483be7d1ce98ff5f7a0ec6e82a7ec959586b3313ee239f" in bootstrap
    assert "b139949c5bd74937ad8ed8c8cf3d9ffb1e99c866c823204dc42c0d91fa181897" in bootstrap
    assert "cd47557a67d7e8f2891d98b5e1dbf2988544569fdf4f1bdb30e92b71aa61b548" in bootstrap


def test_product_docs_track_cloud_workspace_and_agent_tools():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs" / "IMPLEMENTATION_PLAN.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    decisions = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")

    assert "durable multi-device Projects/Library/Memory migration out of browser cache" not in readme
    assert "Move these surfaces behind authenticated server APIs" not in plan
    assert "Playwright is the default browser worker" not in architecture
    assert "OpenCode-compatible worker, one worktree per job" not in decisions

    assert "Projects/Chats/Library/Memory durable server-side" in readme
    assert "/read" in plan and "/search" in plan
    assert "AGENT_REVIEW.md" in architecture
    assert "contents: read" in decisions


def test_public_product_is_instance_isolated_and_has_no_personal_backend_defaults():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    deploy_env = (ROOT / "deploy" / "olivia.env.example").read_text(encoding="utf-8")
    worker = (ROOT / "cloudflare" / "worker.mjs").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "coding-agent.yml").read_text(encoding="utf-8")
    server = (ROOT / "olivia" / "server.py").read_text(encoding="utf-8")

    public_blob = "\n".join([readme, env, deploy_env, worker, workflow, server]).lower()
    assert "simondalmasso44@gmail.com" not in public_blob
    assert "0livia.simondalmasso44.workers.dev" not in public_blob
    assert "olivia_coding_repo=simondalmasso/0livia" not in public_blob

    assert "OLIVIA_CODING_REPO=owner/your-repo" in env
    assert "OLIVIA_CODING_REPO=owner/your-repo" in deploy_env
    assert 'default: "main"' in workflow
    assert 'os.getenv("OLIVIA_CODING_BASE_REF", "main")' in server
    assert "const TRANSITIONAL_BRIDGE_ENABLED = false;" in worker


def test_public_product_docs_define_privacy_self_hosting_and_claims_policy():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    privacy = (ROOT / "docs" / "PRIVACY.md").read_text(encoding="utf-8")
    self_hosting = (ROOT / "docs" / "SELF_HOSTING.md").read_text(encoding="utf-8")

    assert "self-hosted agentic AI workspace" in readme
    assert "zero-cost-first" in readme
    assert "not a guarantee" in readme.lower()
    assert "separate runtime state" in privacy.lower()
    assert "your own provider" in self_hosting.lower()
    assert "private vulnerability" in security.lower()
