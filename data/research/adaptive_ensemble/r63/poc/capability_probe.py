"""Report mechanisms this process can actually arm. No configuration changes."""

from __future__ import annotations

import sys

from lifecycle_contract import (
    CONTAINMENT_UNAVAILABLE,
    DESCENDANT_CONTAINMENT_AVAILABLE,
    DIRECT_CHILD_ONLY,
    REQUIRE_DESCENDANT_CONTAINMENT,
)


def probe_capabilities(requested_policy: str = REQUIRE_DESCENDANT_CONTAINMENT) -> dict[str, object]:
    if sys.platform == "win32":
        import windows_backend

        return windows_backend.probe(requested_policy)
    if sys.platform.startswith("linux"):
        import linux_backend

        return linux_backend.probe(requested_policy)
    return {
        "operating_system": sys.platform,
        "mechanisms": (),
        "requested_policy": requested_policy,
        "descendant_available": False,
        "actual_if_requested": CONTAINMENT_UNAVAILABLE,
        "direct_child_level": DIRECT_CHILD_ONLY,
        "descendant_level": CONTAINMENT_UNAVAILABLE,
        "unsupported": (f"UNSUPPORTED_PLATFORM:{sys.platform}",),
        "detail": "no backend",
    }
