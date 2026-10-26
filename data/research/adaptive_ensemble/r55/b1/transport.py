"""Allowlisted GET sender for the R.55 B1 offline session.

Importing this module does not open a connection. The live client classes are refused.
This file does not enable a live OANDA session.
"""

from __future__ import annotations

import http.client
import ssl
from typing import Any


def _blocked_client(connection_class: Any) -> bool:
    if connection_class is http.client.HTTPSConnection or connection_class is http.client.HTTPConnection:
        return True
    if isinstance(connection_class, type) and issubclass(connection_class, (http.client.HTTPConnection, http.client.HTTPSConnection)):
        return True
    return False


def transmit(prepared: dict[str, Any], connection_class: Any, gate: Any) -> tuple[int, bytes]:
    """Send one allowlisted GET through an offline client class. The live client classes are refused."""
    if not isinstance(connection_class, type) or _blocked_client(connection_class):
        raise gate.Failure("UNEXPECTED")
    _kind, target = gate._target(prepared)
    context = gate.tls_context()
    conn: Any = None
    try:
        conn = connection_class(gate.HOST, gate.PORT, timeout=gate.TIMEOUT_SECONDS, context=context)
        conn.request(
            "GET",
            target,
            body=None,
            headers={"Accept": "application/json", "Authorization": prepared["authorization"]},
        )
        response = conn.getresponse()
        if getattr(response, "status", None) != 200:
            raise gate.Failure("HTTP_ERROR")
        raw = response.read(gate.MAX_BODY + 1)
        if not isinstance(raw, (bytes, bytearray)) or len(raw) > gate.MAX_BODY:
            raise gate.Failure("RESPONSE_TOO_LARGE", http_ok=True)
        return 200, bytes(raw)
    except gate.Failure:
        raise
    except TimeoutError:
        raise gate.Failure("TIMEOUT") from None
    except ssl.SSLError:
        raise gate.Failure("TLS_FAILURE") from None
    except Exception:
        raise gate.Failure("UNEXPECTED") from None
    finally:
        closer = getattr(conn, "close", None)
        if closer is not None:
            try:
                closer()
            except Exception:
                pass
