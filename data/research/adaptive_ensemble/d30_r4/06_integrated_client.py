"""Offline integration of the registry safety policy. No transport."""
from __future__ import annotations

ALLOWED_HOSTS = frozenset({"registry-1.docker.io", "auth.docker.io"})
REGISTRY_HOST = "registry-1.docker.io"
AUTH_HOST = "auth.docker.io"
REPOSITORY = "library/python"
METHOD_BY_HOST = {REGISTRY_HOST: "HEAD", AUTH_HOST: "GET"}
CONNECTION_TIMEOUT_SECONDS = 10
INACTIVITY_TIMEOUT_SECONDS = 15
REQUEST_DEADLINE_SECONDS = 30
STAGE_DEADLINE_SECONDS = 180
MAX_REQUESTS = 20
MAX_HEADS = 16
MAX_TOKEN_GETS = 1
MAX_BODY_BYTES = 1048576
LEDGER_KEYS = ("event", "host", "method", "disposition")


class SafetyStop(Exception):
    def __init__(self, classification: str, reason: str) -> None:
        self.classification = classification
        self.reason = reason
        super().__init__(reason)


class Reject(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def dns_resolution_is_hard_bounded() -> bool:
    return False


class Budget:
    def __init__(self) -> None:
        self.total = 0
        self.head = 0
        self.token = 0
        self.body = 0
        self.redirects_followed = 0
        self.retries = 0
        self.redirects_recorded = 0
        self.dispatch_count = 0

    def reserve(self, host: str, method: str, repository: str, digest: str | None, category: str, allowlist: set[str]) -> int:
        if category in {"storage", "registry_get", "layer_body", "retry"}:
            raise Reject(category)
        if host not in ALLOWED_HOSTS:
            raise Reject("host")
        if repository != REPOSITORY:
            raise Reject("repository")
        if method not in {"HEAD", "GET"}:
            raise Reject("method")
        if host == REGISTRY_HOST and method != "HEAD":
            raise Reject("registry_get")
        if category == "token" and (host != AUTH_HOST or method != "GET"):
            raise Reject("token method")
        if digest is not None and digest not in allowlist:
            raise Reject("digest")
        if self.total >= MAX_REQUESTS:
            raise Reject("total")
        if category == "head" and self.head >= MAX_HEADS:
            raise Reject("head")
        if category == "token" and self.token >= MAX_TOKEN_GETS:
            raise Reject("token")
        self.total += 1
        if category == "head":
            self.head += 1
        if category == "token":
            self.token += 1
        return self.total

    def add_body(self, count: int) -> None:
        if count < 0 or self.body + count > MAX_BODY_BYTES:
            raise Reject("body")
        self.body += count

    def record_redirect(self) -> None:
        self.redirects_recorded += 1


class OfflineClient:
    def __init__(self) -> None:
        self.budget = Budget()
        self.ledger: list[dict[str, str]] = []
        self.network_opened = False

    def discover(self, allowlist: set[str]) -> None:
        del allowlist
        if not dns_resolution_is_hard_bounded():
            self._record({"event": "discover", "disposition": "closed"})
            raise SafetyStop(
                "D30_R4_NETWORK_PATH_CLOSED",
                "name lookup is not hard-bounded and no transport was created",
            )
        raise SafetyStop("D30_R4_NETWORK_PATH_CLOSED", "network path is closed")

    def check_request(self, host: str, method: str, digest: str | None, allowlist: set[str]) -> str:
        if host == "production.cloudfront.docker.com":
            raise SafetyStop("D30_R4_NETWORK_PATH_CLOSED", "storage host is not approved")
        if host not in ALLOWED_HOSTS or METHOD_BY_HOST.get(host) != method:
            raise SafetyStop("D30_R4_NETWORK_PATH_CLOSED", "host or method is not approved")
        if digest is not None and digest not in allowlist:
            raise SafetyStop("D30_R4_NETWORK_PATH_CLOSED", "digest is not on the allowlist")
        return "policy-only"

    def follow_redirect(self, _location: str) -> None:
        self.budget.record_redirect()
        raise SafetyStop("D30_R4_NETWORK_PATH_CLOSED", "redirects are not followed")

    def propose(self, host: str, method: str, repository: str, digest: str | None, category: str, allowlist: set[str]) -> str:
        self.budget.reserve(host, method, repository, digest, category, allowlist)
        self._record({"event": "propose", "host": host, "method": method, "disposition": "not-dispatched"})
        return "not-dispatched"

    def _record(self, raw: dict[str, str]) -> None:
        cleaned = {}
        for key in LEDGER_KEYS:
            value = raw.get(key)
            if value is None:
                continue
            if not isinstance(value, str) or any(marker in value for marker in ("redact-me", "Bearer", "Authorization")):
                cleaned[key] = "rejected"
            else:
                cleaned[key] = value
        self.ledger.append(cleaned)
