"""Reduced-policy eligibility for one audited diagnostic worker.

The allowlist is the SHA-256 of the R.61 worker and the four modules it loads.
There is no global bypass. A changed byte removes eligibility. Eligibility is
not descendant containment and is not an operational switch.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

AUDITED_SHA256 = {
    "diagnostic_worker.py": "0f70dcf2a9d6a1d7cd12f285bb6396c4aa0163148dc4943bc419d6743ab1020e",
    "credential_ipc.py": "b4630c5b74dd0d9f73bce1f707f3b2391bffd0fe746d5b74447e728a4ced4d1b",
    "live_session_gate.py": "2f89959f8cae0e45589b16d159f038af370aa9cec592455784046ef57230c4c0",
    "restricted_live_transport.py": "b56d94edaf8d4d7ed2ae366efc6587aab9c49d7841aeef9bc5fdc7429f6d6f10",
    "metadata_extract.py": "06561e7e8fd5fb5278929f2edfad0b18ce8c7ec5d7f4a4f13bb2c1b647bbafd3",
}

DIRECT_CHILD_ONLY_EXPLICIT = "DIRECT_CHILD_ONLY_EXPLICIT"


def evaluate(directory: Path) -> dict[str, object]:
    mismatches: list[str] = []
    missing: list[str] = []
    observed: dict[str, str] = {}
    for name, expected in AUDITED_SHA256.items():
        path = directory / name
        if not path.is_file():
            missing.append(name)
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        observed[name] = digest
        if digest != expected:
            mismatches.append(name)
    eligible = not missing and not mismatches
    return {
        "eligible": eligible,
        "policy_if_explicitly_selected": DIRECT_CHILD_ONLY_EXPLICIT if eligible else "NOT_ELIGIBLE",
        "global_bypass": False,
        "equivalent_to_descendant_containment": False,
        "default_policy": "REQUIRE_DESCENDANT_CONTAINMENT",
        "mismatches": tuple(mismatches),
        "missing": tuple(missing),
        "observed": observed,
        "bound_to": "r61-diagnostic-worker-and-four-loaded-modules",
    }
