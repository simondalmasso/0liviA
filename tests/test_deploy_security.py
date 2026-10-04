from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = (ROOT / "deploy" / "bootstrap-a1.sh").read_text(encoding="utf-8")
CLOUD_INIT = (ROOT / "deploy" / "cloud-init-a1.yaml").read_text(encoding="utf-8")


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
