"""Read-only OpenShell host suitability; never installs, starts or executes a sandbox.

Actual runtime activation is forbidden until a separate pinned version,
policy prover and live isolation acceptance on a cost-certified host.
"""
from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OpenShellReadiness:
    platform: str
    memory_available_mib: int | None
    cli_present: bool
    container_runtime_present: bool
    cost_gate_confirmed: bool
    host_gate_confirmed: bool
    ready_for_manual_benchmark: bool
    production_active: bool = False


def memory_available_mib(meminfo: Path = Path("/proc/meminfo")) -> int | None:
    try:
        lines = meminfo.read_text(encoding="ascii").splitlines()
        values = [s.split() for s in lines if s.startswith("MemAvailable:")]
        return int(values[0][1]) // 1024 if len(values) == 1 else None
    except (OSError, ValueError, IndexError):
        return None


def inspect_openshell_host(*, system: str | None = None,
                           available_mib: int | None = None,
                           cli: str | None = None,
                           engine: str | None = None,
                           cost_confirmed: bool | None = None,
                           host_confirmed: bool | None = None) -> OpenShellReadiness:
    """Return conservative readiness. No process, shell, network or file changes.

    4096 MiB is a *preliminary* screening threshold, not a resource benchmark.
    Even 'ready' cannot activate a sandbox; kernel/OCI/policy gates remain.
    """
    system = platform.system() if system is None else system
    available = memory_available_mib() if available_mib is None else available_mib
    cli = shutil.which("openshell") if cli is None else cli
    engine = (shutil.which("docker") or shutil.which("podman")) if engine is None else engine
    cost = (os.getenv("OLIVIA_OPENSHELL_ZERO_COST_CONFIRMED") == "1"
            if cost_confirmed is None else cost_confirmed)
    host = (os.getenv("OLIVIA_OPENSHELL_HOST_APPROVED") == "1"
            if host_confirmed is None else host_confirmed)
    eligible = bool(system == "Linux" and available is not None and available >= 4096
                    and cli and engine and cost and host)
    return OpenShellReadiness(
        platform=system,
        memory_available_mib=available,
        cli_present=bool(cli),
        container_runtime_present=bool(engine),
        cost_gate_confirmed=bool(cost),
        host_gate_confirmed=bool(host),
        ready_for_manual_benchmark=eligible,
    )
