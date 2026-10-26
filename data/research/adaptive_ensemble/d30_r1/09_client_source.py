"""D.30-R1 stage-specific HEAD safety shell. It does not open a socket."""
from __future__ import annotations

import threading
import time

ALLOWED_HOSTS = frozenset({"registry-1.docker.io", "auth.docker.io"})
REGISTRY_HOST = "registry-1.docker.io"
AUTH_HOST = "auth.docker.io"
REPOSITORY = "library/python"
TOKEN_SCOPE = "repository:library/python:pull"
METHOD_BY_HOST = {REGISTRY_HOST: "HEAD", AUTH_HOST: "GET"}
CONNECTION_TIMEOUT_SECONDS = 10
INACTIVITY_TIMEOUT_SECONDS = 15
REQUEST_DEADLINE_SECONDS = 30
STAGE_DEADLINE_SECONDS = 180
MAX_REQUESTS = 20
MAX_HEADS = 16
MAX_TOKEN_GETS = 1
MAX_BODY_BYTES = 1048576
MAX_REDIRECTS_FOLLOWED = 0
MAX_RETRIES = 0
STORAGE_HOSTS_CONTACTED = 0


class SafetyStop(Exception):
    def __init__(self, classification: str, reason: str) -> None:
        self.classification = classification
        super().__init__(reason)


def dns_resolution_is_hard_bounded() -> bool:
    """socket.getaddrinfo cannot be cancelled by a socket timeout."""
    return False


def check_request(host: str, method: str, digest: str | None, allowlist: set[str]) -> None:
    if host not in ALLOWED_HOSTS or METHOD_BY_HOST.get(host) != method:
        raise SafetyStop("D30_R1_BLOCKED_CLIENT_SAFETY", "host or method is not approved")
    if host == REGISTRY_HOST and method != "HEAD":
        raise SafetyStop("D30_R1_BLOCKED_CLIENT_SAFETY", "registry GET is not approved")
    if host == AUTH_HOST and method != "GET":
        raise SafetyStop("D30_R1_BLOCKED_CLIENT_SAFETY", "token method is not approved")
    if digest is not None and digest not in allowlist:
        raise SafetyStop("D30_R1_BLOCKED_CLIENT_SAFETY", "digest is not on the allowlist")
    if host == "production.cloudfront.docker.com":
        raise SafetyStop("D30_R1_BLOCKED_UNAPPROVED_REDIRECT", "storage host is not approved")


def follow_redirect(_location: str) -> None:
    raise SafetyStop("D30_R1_BLOCKED_UNAPPROVED_REDIRECT", "redirects are not followed")


def demonstrate_resolver_not_cancellable(sleep_seconds: float, deadline_seconds: float) -> dict[str, object]:
    state = {"finished": False}

    def resolver() -> None:
        time.sleep(sleep_seconds)
        state["finished"] = True

    worker = threading.Thread(target=resolver)
    started = time.monotonic()
    worker.start()
    worker.join(deadline_seconds)
    caller_wait = time.monotonic() - started
    still_running = worker.is_alive()
    worker.join()
    return {
        "caller_wait_seconds": round(caller_wait, 3),
        "deadline_seconds": deadline_seconds,
        "resolver_still_running_at_deadline": still_running,
        "resolver_cancelled": False,
        "resolver_finished_after_wait": state["finished"],
    }


def discover(allowlist: set[str]) -> None:
    if not dns_resolution_is_hard_bounded():
        raise SafetyStop(
            "D30_R1_BLOCKED_CLIENT_SAFETY",
            "DNS resolution cannot be hard-bounded by the standard library",
        )
    if not allowlist:
        raise SafetyStop("D30_R1_BLOCKED_CLIENT_SAFETY", "empty allowlist")
    raise SafetyStop("D30_R1_BLOCKED_CLIENT_SAFETY", "network path is closed")
