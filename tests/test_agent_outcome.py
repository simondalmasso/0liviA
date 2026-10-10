from olivia.agent_outcome import classify_external_run_status


def test_agent_claim_of_success_requires_actual_remote_receipt():
    assert classify_external_run_status({
        "remote_status": "completed", "remote_conclusion": "success",
        "remote_run_id": 123,
    }) == "succeeded"
    for payload in (
        {"remote_status": "completed", "remote_conclusion": "success"},
        {"remote_status": "completed", "remote_conclusion": "success", "remote_run_id": 0},
        {"remote_status": "completed", "remote_conclusion": "success", "remote_run_id": "claimed"},
        {"remote_status": "completed", "remote_conclusion": "success", "remote_run_id": True},
        {"remote_status": "completed", "remote_conclusion": "done by model"},
    ):
        assert classify_external_run_status(payload) != "succeeded"


def test_agent_unknown_and_failure_states_fail_closed():
    assert classify_external_run_status({"remote_status": "completed", "remote_conclusion": "failure"}) == "failed"
    assert classify_external_run_status({"remote_status": "completed", "remote_conclusion": "weird"}) == "unknown"
    assert classify_external_run_status({"remote_status": "in_progress"}) == "in_progress"
    assert classify_external_run_status({"remote_status": "not_a_status"}) == "unknown"
    assert classify_external_run_status({"remote_status": "completed", "remote_conclusion": "cancelled"}) == "failed"


def test_miniagi_raw_shell_not_imported():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    body = (root / "olivia/agent_outcome.py").read_text(encoding="utf-8")
    assert "subprocess" not in body
    assert "eval(" not in body
    assert "exec(" not in body
    assert "urlopen" not in body
