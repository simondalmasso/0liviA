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


def test_env_examples_document_owner_cookie_auth_without_plaintext_password():
    for path in (ROOT / ".env.example", ROOT / "deploy" / "olivia.env.example"):
        content = path.read_text(encoding="utf-8")
        assert "OLIVIA_OWNER_PASSWORD_VERIFIER=" in content
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


def test_coding_agent_never_receives_repository_admin_write_credentials():
    workflow = (ROOT / ".github" / "workflows" / "coding-agent.yml").read_text(encoding="utf-8")
    code_segment = workflow.split("jobs:\n  code:", 1)[1].split("\n  publish:", 1)[0]
    publish_segment = workflow.split("\n  publish:", 1)[1]

    assert "contents: write" not in code_segment
    assert "persist-credentials: false" in code_segment
    assert "github.token" not in code_segment
    assert "NVIDIA_API_KEY" not in publish_segment
    assert "contents: write" in publish_segment


def test_chatgpt_plan_docs_match_implemented_onboarding():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs" / "IMPLEMENTATION_PLAN.md").read_text(encoding="utf-8")
    security = (ROOT / "docs" / "SECURITY_AUDIT.md").read_text(encoding="utf-8")
    research = (ROOT / "docs" / "RESEARCH.md").read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "CHATGPT_PLAN.md").read_text(encoding="utf-8")

    assert "Implement the one-time local Sign in with ChatGPT OAuth onboarding helper" not in plan
    assert "OAuth onboarding/JWKS validation is not yet integrated" not in security
    assert "one-time OAuth onboarding remains a release gate" not in research
    assert "one-time local Sign in with ChatGPT OAuth helper" in readme
    assert "PKCE" in runbook and "JWKS" in runbook
    assert "no_credit_overage_verified" in runbook


def test_github_actions_are_pinned_to_immutable_commits():
    import re

    workflows = ROOT / ".github" / "workflows"
    action_ref = re.compile(r"^\s*uses:\s+(actions/[^@\s]+)@([^\s#]+)", re.MULTILINE)
    unpinned = []
    for path in workflows.glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        for action, ref in action_ref.findall(text):
            if not re.fullmatch(r"[0-9a-f]{40}", ref):
                unpinned.append(f"{path.name}: {action}@{ref}")
    assert unpinned == []


def test_browser_worker_examples_fail_closed_on_privacy_and_cost():
    for path in (ROOT / ".env.example", ROOT / "deploy" / "olivia.env.example"):
        text = path.read_text(encoding="utf-8")
        assert "OLIVIA_BROWSER_ZERO_COST_VERIFIED=0" in text
        assert "private" in text.lower()
        assert "configured public repo" not in text.lower()
