"""Fixed-host GET transport for injected offline doubles.

The live factory is sealed. Gate 2 does not call getaddrinfo, connect, or wrap a socket.
Phase budgets are wall-clock limits passed into each double call and checked between body chunks.
A call that ignores its timeout cannot be preempted here. Process isolation is not used.
"""

from __future__ import annotations

import importlib.util
import ssl
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REDIRECTS = frozenset({301, 302, 303, 307, 308})
GRACE_SECONDS = 0.15
CHUNK = 8192


def _load(stem: str) -> Any:
    name = f"r55g2_{stem}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, HERE / f"{stem}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def require_tls(context: object) -> None:
    """Accept only a context that requires certificate and hostname checks."""
    gate = _load("request_gate")
    if context is None:
        raise gate.GateRejected(gate.REJECTED)
    if getattr(context, "verify_mode", None) != ssl.CERT_REQUIRED:
        raise gate.GateRejected(gate.REJECTED)
    if getattr(context, "check_hostname", None) is not True:
        raise gate.GateRejected(gate.REJECTED)


def sealed_live_factory(*_args: object, **_kwargs: object) -> None:
    """Present so a live constructor has a name. Calling it does not open a socket."""
    gate = _load("request_gate")
    raise gate.GateRejected(gate.LIVE_TRANSPORT_NOT_ACTIVATED)


def _offline(connection: object) -> bool:
    doubles = _load("synthetic_test_doubles")
    return isinstance(connection, doubles.OfflineDouble) and bool(getattr(connection, "offline_only", False))


def _phase(clock: Any, fn: Callable[[float], Any]) -> Any:
    gate = _load("request_gate")
    budget, reason = clock.phase_budget()
    started = clock.now()
    try:
        result = fn(budget)
    except TimeoutError:
        raise gate.GateRejected(reason) from None
    except gate.GateRejected:
        raise
    except Exception:
        raise gate.GateRejected(gate.REJECTED) from None
    if clock.now() - started > budget + GRACE_SECONDS:
        raise gate.GateRejected(reason)
    return result


def _status_code(status: int) -> str | None:
    if status == 200:
        return None
    if status == 401:
        return "HTTP_401"
    if status == 403:
        return "HTTP_403"
    if status == 404:
        return "HTTP_404"
    if status == 429:
        return "HTTP_429"
    if 500 <= status <= 599:
        return "HTTP_5XX"
    return "HTTP_ERROR"


def execute_description(
    factory: Callable[[], object],
    description: dict[str, object],
    account_id: str,
    token: str,
    clock: Any,
    context: object,
) -> tuple[int, bytes]:
    """Validate, then construct one offline double, then perform one GET.

    A rejected description or TLS context does not call the factory.
    The token is not passed to the double and is not placed in an exception.
    """
    gate = _load("request_gate")
    doubles = _load("synthetic_test_doubles")
    gate.validate_description(description, account_id)
    require_tls(context)
    if not isinstance(token, str) or token == "":
        raise gate.GateRejected(gate.REJECTED)
    if factory is sealed_live_factory:
        raise gate.GateRejected(gate.LIVE_TRANSPORT_NOT_ACTIVATED)
    kind = str(description["path_pattern"]).rpartition("/")[2]
    connection: object | None = None
    header = ""
    try:
        connection = factory()
        if not _offline(connection):
            raise gate.GateRejected(gate.REJECTED)
        clock.start_request()
        _phase(clock, lambda budget: connection.resolve(gate.HOST, gate.PORT, budget))
        _phase(clock, lambda budget: connection.connect(budget))
        _phase(clock, lambda budget: connection.handshake(budget))
        path = f"/v3/accounts/{account_id}/{kind}"
        query = dict(description["query"])  # type: ignore[arg-type]
        header = "Bearer " + token
        present = header.startswith("Bearer ") and len(token) > 0
        header = ""

        def _send(budget: float) -> None:
            connection.send_get(path, query, budget, present)

        _phase(clock, _send)
        status = _phase(clock, lambda budget: connection.read_headers(budget))
        if not isinstance(status, int):
            raise gate.GateRejected(gate.REJECTED)
        if status in REDIRECTS:
            raise gate.GateRejected("REDIRECT_NOT_FOLLOWED", {"http_status": str(status)})
        failure = _status_code(status)
        if failure is not None:
            raise gate.GateRejected(failure, {"http_status": str(status)})
        buf = bytearray()
        while True:
            budget, reason = clock.phase_budget()
            started = clock.now()
            try:
                chunk = connection.read_chunk(budget, CHUNK)
            except TimeoutError:
                buf.clear()
                raise gate.GateRejected(reason) from None
            except gate.GateRejected:
                buf.clear()
                raise
            except Exception:
                buf.clear()
                raise gate.GateRejected(gate.REJECTED) from None
            if clock.now() - started > budget + GRACE_SECONDS:
                buf.clear()
                raise gate.GateRejected(reason)
            if not isinstance(chunk, (bytes, bytearray)) or chunk == b"":
                break
            buf.extend(chunk)
            if len(buf) > gate.MAX_BODY:
                buf.clear()
                raise gate.GateRejected("RESPONSE_TOO_LARGE", {"http_status": "200"})
        return status, bytes(buf)
    finally:
        header = ""
        if connection is not None and hasattr(connection, "close"):
            try:
                connection.close()
            except Exception:
                pass
