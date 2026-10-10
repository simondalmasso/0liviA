#!/usr/bin/env python3
"""Non-mutating OpenShell host preflight. Does not execute OpenShell."""
from __future__ import annotations

import json
from dataclasses import asdict

from olivia.openshell import inspect_openshell_host

if __name__ == "__main__":
    print(json.dumps(asdict(inspect_openshell_host()), sort_keys=True))
