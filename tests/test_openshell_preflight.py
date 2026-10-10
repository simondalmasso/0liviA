"""OpenShell integration must remain opt-in and fail closed."""
from dataclasses import asdict
from pathlib import Path

from olivia.openshell import inspect_openshell_host, memory_available_mib

ROOT = Path(__file__).resolve().parents[1]


def test_meminfo_parsing(tmp_path):
    f = tmp_path / "meminfo"
    f.write_text("MemTotal: 123456 kB\nMemAvailable: 1048576 kB\n")
    assert memory_available_mib(f) == 1024
    f.write_text("MemAvailable: unknown kB\n")
    assert memory_available_mib(f) is None


def test_openshell_preflight_requires_cost_host_tools_and_ram():
    valid = dict(system="Linux", available_mib=5000, cli="/usr/bin/openshell",
                 engine="/usr/bin/docker", cost_confirmed=True, host_confirmed=True)
    result = inspect_openshell_host(**valid)
    assert result.ready_for_manual_benchmark
    assert not result.production_active
    for key, value in (("available_mib", 1024), ("system", "Windows"),
                       ("cli", ""), ("engine", ""), ("cost_confirmed", False),
                       ("host_confirmed", False)):
        test = dict(valid)
        test[key] = value
        assert not inspect_openshell_host(**test).ready_for_manual_benchmark


def test_openshell_no_spontaneous_activation(monkeypatch):
    monkeypatch.delenv("OLIVIA_OPENSHELL_HOST_APPROVED", raising=False)
    monkeypatch.delenv("OLIVIA_OPENSHELL_ZERO_COST_CONFIRMED", raising=False)
    status = inspect_openshell_host(system="Linux", available_mib=5000,
                                    cli="/usr/bin/openshell", engine="/bin/docker")
    assert status.cost_gate_confirmed is False
    assert status.host_gate_confirmed is False
    assert status.ready_for_manual_benchmark is False
    assert asdict(status)["production_active"] is False


def test_openshell_policy_is_narrow_and_no_prod_runner():
    policy = (ROOT / "deploy/openshell/olivia-readonly-policy.yaml").read_text()
    assert "include_workdir: false" in policy
    assert "compatibility: hard_requirement" in policy
    assert "compatibility: best_effort" not in policy
    assert "api.github.com" in policy
    assert "access: read-only" in policy
    assert "protocol: rest" in policy
    assert "host: github.com" not in policy
    assert "api.anthropic.com" not in policy
