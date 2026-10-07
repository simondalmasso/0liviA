from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = (ROOT / "deploy" / "bootstrap-a1.sh").read_text(encoding="utf-8")
CLOUD_INIT = (ROOT / "deploy" / "cloud-init-a1.yaml").read_text(encoding="utf-8")
CHATGPT_INSTALLER = (ROOT / "scripts" / "install_chatgpt_plan_profile.sh").read_text(encoding="utf-8")
SMOKE = (ROOT / "deploy" / "smoke.sh").read_text(encoding="utf-8")
PREFLIGHT = (ROOT / "deploy" / "preflight.sh").read_text(encoding="utf-8")
CANONICAL_DEPLOY = (ROOT / ".github" / "workflows" / "deploy-canonical.yml").read_text(encoding="utf-8")


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
    assert '"name":"local-recovery-qwen"' in BOOTSTRAP
    assert '"priority":1000' in BOOTSTRAP


def test_new_install_has_no_unverified_external_chat_lane():
    assert "ANON_CHAT_ENABLED" not in BOOTSTRAP
    assert "pollinations-anon" not in BOOTSTRAP
    assert "text.pollinations.ai" not in BOOTSTRAP
    assert 'PROVIDERS_JSON=\'[]\'' in BOOTSTRAP
    assert '"name":"local-recovery-qwen"' in BOOTSTRAP
    assert '"cost_mode":"local"' in BOOTSTRAP
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


def test_bootstrap_exports_exact_build_sha():
    bootstrap = (ROOT / "deploy" / "bootstrap-a1.sh").read_text(encoding="utf-8")
    assert "SOURCE_SHA=" in bootstrap
    assert "OLIVIA_BUILD_SHA=${SOURCE_SHA}" in bootstrap


def test_release_smoke_requires_exact_canonical_zero_cost_build():
    assert "EXPECTED_SHA" in SMOKE
    assert '"api_mode": body.get("api_mode") == "canonical"' in SMOKE
    assert '"build_sha": str(body.get("build_sha") or "").lower() == expected' in SMOKE
    assert '"hard_zero_cost": body.get("hard_zero_cost") is True' in SMOKE
    assert '"provider_ready": body.get("provider_ready") is True' in SMOKE
    assert '"owner_auth_configured": body.get("owner_auth_configured") is True' in SMOKE
    assert '"registration_closed": body.get("registration_open") is False' in SMOKE
    assert 'allowed_modes = {"local", "free_hard_cap", "plan_included"}' in SMOKE
    assert 'event.get("type") == "route"' in SMOKE
    assert 'event.get("type") == "done"' in SMOKE


def test_bootstrap_uses_versioned_atomic_releases_and_per_release_venv():
    service = (ROOT / "deploy" / "0livia.service").read_text(encoding="utf-8")
    assert 'RELEASES_ROOT="${APP_ROOT}/releases"' in BOOTSTRAP
    assert 'RELEASE_DIR="${RELEASES_ROOT}/${SOURCE_SHA}"' in BOOTSTRAP
    assert 'STAGE_DIR="${RELEASES_ROOT}/.${SOURCE_SHA}.stage.${BASHPID}"' in BOOTSTRAP
    assert 'ln -s "${RELEASE_DIR}" "${APP_ROOT}/.current.next"' in BOOTSTRAP
    assert 'mv -Tf "${APP_ROOT}/.current.next" "${APP_ROOT}/current"' in BOOTSTRAP
    assert 'PREVIOUS_RELEASE=' in BOOTSTRAP
    assert 'rollback_release()' in BOOTSTRAP
    assert '"${RELEASE_DIR}/venv/bin/pip" install "${RELEASE_DIR}"' in BOOTSTRAP
    assert 'touch "${RELEASE_DIR}/.ready"' in BOOTSTRAP
    assert 'test -f "${RELEASE_DIR}/.ready"' in BOOTSTRAP
    assert "ExecStart=/opt/0livia/current/venv/bin/python -m olivia.server" in service
    assert "/opt/0livia/venv/bin/python" not in service


def test_bootstrap_preserves_existing_runtime_env_on_upgrade():
    assert 'ENV_FILE="${ETC_ROOT}/olivia.env"' in BOOTSTRAP
    assert 'if [[ -f "${ENV_FILE}" ]]; then' in BOOTSTRAP
    assert 'OLIVIA_BUILD_SHA' in BOOTSTRAP
    assert 'OLIVIA_HARD_ZERO_COST' in BOOTSTRAP
    assert 'preserve the configured provider catalog and signing token' in BOOTSTRAP
    assert 'ENV_BACKUP="${tmp}/olivia.env.previous"' in BOOTSTRAP
    assert 'cp -a "${ENV_FILE}" "${ENV_BACKUP}"' in BOOTSTRAP
    assert 'cp -a "${ENV_BACKUP}" "${ETC_ROOT}/olivia.env"' in BOOTSTRAP


def test_bootstrap_restarts_new_release_and_rolls_back_on_failed_health():
    assert "systemctl restart olivia" in BOOTSTRAP
    assert 'if ! wait_for_core; then' in BOOTSTRAP
    assert 'rollback_release' in BOOTSTRAP
    assert 'systemctl restart olivia || true' in BOOTSTRAP



def test_canonical_deploy_workflow_is_exact_sha_and_pinned_ssh_only():
    assert "workflow_dispatch:" in CANONICAL_DEPLOY
    assert "RELEASE_SHA:" in CANONICAL_DEPLOY
    assert '[[ "$RELEASE_SHA" =~ ^[0-9a-fA-F]{40}$ ]]' in CANONICAL_DEPLOY
    assert 'git merge-base --is-ancestor "$RELEASE_SHA" origin/main' in CANONICAL_DEPLOY
    assert "OLIVIA_DEPLOY_HOST" in CANONICAL_DEPLOY
    assert "OLIVIA_DEPLOY_USER" in CANONICAL_DEPLOY
    assert "OLIVIA_DEPLOY_SSH_KEY" in CANONICAL_DEPLOY
    assert "OLIVIA_DEPLOY_KNOWN_HOSTS" in CANONICAL_DEPLOY
    assert "StrictHostKeyChecking=yes" in CANONICAL_DEPLOY
    assert "PasswordAuthentication=no" in CANONICAL_DEPLOY
    assert "REF='$RELEASE_SHA'" in CANONICAL_DEPLOY
    assert "http://127.0.0.1:8080/healthz" in CANONICAL_DEPLOY
    assert '"hard_zero_cost": body.get("hard_zero_cost") is True' in CANONICAL_DEPLOY
    assert "SETUP_URL" not in CANONICAL_DEPLOY
    assert "cloudflare" not in CANONICAL_DEPLOY.casefold()


def test_canonical_host_preflight_fails_closed_before_bootstrap():
    assert "PREFLIGHT_OK=YES" in PREFLIGHT
    assert "passwordless_sudo_required" in PREFLIGHT
    assert "OLIVIA_PREFLIGHT_MIN_MEMORY_MB" in PREFLIGHT
    assert "OLIVIA_PREFLIGHT_MIN_DISK_MB" in PREFLIGHT
    assert "fallocate_missing_for_micro" in PREFLIGHT
    assert "mkswap_missing_for_micro" in PREFLIGHT
    assert "swapon_missing_for_micro" in PREFLIGHT
    assert "Preflight target before mutation" in CANONICAL_DEPLOY
    assert "'bash -s' < deploy/preflight.sh" in CANONICAL_DEPLOY
    assert CANONICAL_DEPLOY.index("Preflight target before mutation") < CANONICAL_DEPLOY.index("Upload exact bootstrap script")


def test_bootstrap_rolls_back_first_install_and_public_https_failures():
    assert 'rm -f "${APP_ROOT}/current"' in BOOTSTRAP
    assert "systemctl stop olivia || true" in BOOTSTRAP
    assert 'CADDY_BACKUP=' in BOOTSTRAP
    assert 'cp -a "${CADDY_BACKUP}" "${CADDY_FILE}"' in BOOTSTRAP
    assert "wait_for_public_https()" in BOOTSTRAP
    assert 'if ! wait_for_public_https; then' in BOOTSTRAP
    assert 'public HTTPS health check failed; previous release restored' in BOOTSTRAP
