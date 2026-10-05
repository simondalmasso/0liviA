from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = (ROOT / "deploy" / "bootstrap-a1.sh").read_text(encoding="utf-8")
CLOUD_INIT = (ROOT / "deploy" / "cloud-init-a1.yaml").read_text(encoding="utf-8")
CHATGPT_INSTALLER = (ROOT / "scripts" / "install_chatgpt_plan_profile.sh").read_text(encoding="utf-8")


def test_cloud_init_requires_immutable_commit_ref_before_root_execution():
    assert 'REF="${REF:-arch/gpt-synthesis-v1}"' not in CLOUD_INIT
    assert "40" in CLOUD_INIT and "commit SHA" in CLOUD_INIT
    assert "raw.githubusercontent.com/simondalmasso/0liviA" in CLOUD_INIT


def test_bootstrap_pins_and_verifies_runtime_and_model_artifacts():
    for digest in (
        "9f454c895ab49d4173cfb3995a39e4f8fe21b364787db8e1ca2778ee7f39aa36",
        "43bfc230e612d20efd483be7d1ce98ff5f7a0ec6e82a7ec959586b3313ee239f",
        "b139949c5bd74937ad8ed8c8cf3d9ffb1e99c866c823204dc42c0d91fa181897",
        "cd47557a67d7e8f2891d98b5e1dbf2988544569fdf4f1bdb30e92b71aa61b548",
    ):
        assert digest in BOOTSTRAP
    assert "sha256sum -c -" in BOOTSTRAP


def test_bootstrap_uses_first_run_registration_without_exposing_gateway_token():
    assert "OLIVIA_OWNER_PASSWORD_VERIFIER=" not in BOOTSTRAP
    assert "/root/0livia-owner-password" not in BOOTSTRAP
    assert "REGISTRATION=first-run" in BOOTSTRAP
    info_block = BOOTSTRAP.split('cat > "${STATE_ROOT}/bootstrap-info"', 1)[1]
    assert "TOKEN=${TOKEN}" not in info_block


def test_bootstrap_protects_first_registration_with_setup_link():
    assert "OLIVIA_REGISTRATION_TOKEN=" in BOOTSTRAP
    assert "SETUP_URL=https://${HOST}/#setup=${REGISTRATION_TOKEN}" in BOOTSTRAP
    assert "chmod 0600" in BOOTSTRAP
    assert 'echo "0liviA bootstrap complete: https://${HOST}"' in BOOTSTRAP
    assert 'echo "0liviA bootstrap complete: https://${HOST}/#setup=' not in BOOTSTRAP


def test_small_local_model_is_recovery_only_by_default():
    assert 'LOCAL_RECOVERY_ENABLED="${LOCAL_RECOVERY_ENABLED:-0}"' in BOOTSTRAP
    assert 'PROVIDERS_JSON=\'[]\'' in BOOTSTRAP
    assert 'if [[ "${LOCAL_RECOVERY_ENABLED}" == "1" ]]; then' in BOOTSTRAP
    assert '"name":"local-recovery-qwen"' in BOOTSTRAP
    assert '"priority":1000' in BOOTSTRAP
    assert 'systemctl disable --now llama-local' in BOOTSTRAP
    assert "never silently downgrades normal chat quality" in BOOTSTRAP


def test_chatgpt_plan_installer_is_fail_closed_and_never_echoes_tokens():
    assert "OLIVIA_CHATGPT_NO_CREDIT_OVERAGE_VERIFIED" in CHATGPT_INSTALLER
    assert "chatgpt.tokens.use.direct" in CHATGPT_INSTALLER
    assert 'install -o olivia -g olivia -m 0600' in CHATGPT_INSTALLER
    assert '"kind": "chatgpt_plan"' in CHATGPT_INSTALLER
    assert '"cost_mode": "plan_included"' in CHATGPT_INSTALLER
    assert '"no_credit_overage_verified": True' in CHATGPT_INSTALLER
    assert "access_token" not in CHATGPT_INSTALLER.split("print(model)", 1)[1]
    assert "refresh_token" not in CHATGPT_INSTALLER.split("print(model)", 1)[1]


def test_caddy_overwrites_client_ip_header_for_login_throttling():
    caddy = (ROOT / "deploy" / "Caddyfile.example").read_text(encoding="utf-8")
    bootstrap = (ROOT / "deploy" / "bootstrap-a1.sh").read_text(encoding="utf-8")
    expected = "header_up X-Olivia-Client-IP {http.request.remote.host}"
    assert expected in caddy
    assert expected in bootstrap


def test_chatgpt_plan_installer_requires_provider_health_confirmation():
    assert '"provider_ready"' in CHATGPT_INSTALLER
    assert '"provider_catalog"' in CHATGPT_INSTALLER
    assert '"chatgpt-plan"' in CHATGPT_INSTALLER
    assert "installed ChatGPT plan provider is not ready" in CHATGPT_INSTALLER
