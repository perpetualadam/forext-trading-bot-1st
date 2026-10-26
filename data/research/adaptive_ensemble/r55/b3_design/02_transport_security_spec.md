# Transport security specification

The values below are the proposed future transport. In the current B2 code they are configured constants or description checks. They are not enforced against a socket. `timeout_enforcement` is `NOT_IMPLEMENTED_OFFLINE`. This document does not claim that a session deadline is enforced.

| Requirement | Configured now | Enforced against a connection now | Future enforcement | Future offline test |
| --- | --- | --- | --- | --- |
| Host `api-fxtrade.oanda.com` | Yes, in the planner | No socket is opened | Compare the description, then pass only that host to the client constructor. Reject any other host before `getaddrinfo`. | Fake description with another host raises before the fake client is constructed. |
| Port 443 | Yes | No | Same as host. | Port 80 rejected before construction. |
| HTTPS only | Implied by the host and port design | No | Do not call `HTTPConnection`. Require a TLS context. | A plain HTTP client class is rejected. |
| Certificate verification | Listed as `REQUIRED` | No | `ssl.create_default_context` for server auth, then refuse the context unless `verify_mode` is `CERT_REQUIRED`. | A context with `CERT_NONE` raises before the request. |
| Hostname verification | Listed as `REQUIRED` | No | Refuse the context unless `check_hostname` is true. | A context with hostname checks off raises. |
| GET only | Yes | No | Method must be `GET` before the client exists. | POST, PUT, PATCH, and DELETE raise before construction. |
| Option A paths | Yes | No | Only the two path patterns. The account segment is inserted in memory and is not written to the report. | Summary, orders, trades, positions, transactions, and candles raise. |
| Query allowlist | Yes | No | Instruments: `instruments` only. Pricing: `instruments` and `includeHomeConversions=true` only. The six names stay in fixed order. | An extra query key raises. |
| No body | Yes | No | `body` is `None`. | A non-empty body raises. |
| No streaming | Yes | No | `stream` is false. | `stream` true raises. |
| No redirects | Yes | No | Do not follow 301, 302, 303, 307, or 308. Do not read those bodies. | A 302 fake response increments attempts by one and does not open a second host. |
| No retries | Yes | No | `retries` is 0, including after 429. | A 429 is one attempt and stops. |
| No URL override | Yes | No | The planner does not accept a raw URL. | A full URL argument raises. |
| Maximum two attempts | Yes, the planner returns two descriptions | The offline loop stops at two records | The controller iterates those two descriptions and no other. | A third fake response is never read. |
| 1 MiB body | Constant `1_048_576` | The offline parser checks a supplied buffer. It does not read a socket. | Read `MAX_BODY + 1`. Longer than 1 MiB is `RESPONSE_TOO_LARGE` and the extra bytes are not stored. | A buffer of that size plus one byte fails and is absent from the output. |
| 5-second per-request timeout | Constant `5.0` | Not applied to a socket | Set the client timeout to 5 seconds for the connection and the read of that one request. | A fake client that blocks raises `TIMEOUT` and is closed. |
| 15-second total deadline | Constant `15.0` | **Not enforced.** | A monotonic clock starts when the session leaves confirmation and covers DNS, TCP, TLS, write, read, and local parse for both requests. At the deadline, close the socket and do not start the next request. | A fake clock or a blocked first call must stop the session without a second call. Until that test exists, the deadline is only a configured number. |
| Sanitised errors | Yes, fixed codes | Yes for the offline parser | Exception text stays a fixed code. No token, account identifier, URL, or body. | A body containing the synthetic secret is absent from the exception and the file. |
| No orders or account changes | Banned kinds | No | Those paths never reach the client. | See the path tests above. |

## Deadlines and the network phases

DNS lookup, TCP connect, TLS handshake, request write, and response read can all block. A future client timeout of 5 seconds limits one request's socket operations only to the extent the chosen client applies that timeout to each of those phases. That behaviour is **DOCUMENTATION_VERIFICATION_REQUIRED** for the exact standard-library client, and it is not implemented here.

The 15-second deadline is a separate session budget. It must be checked before DNS, before connect, before the read, and before request 2. Closing the socket is the cancellation mechanism. Local parse time counts toward the same budget so a huge but legal body cannot run on after the network has finished.

Two 5-second request caps can add up to 10 seconds of socket time. The extra 5 seconds in the 15-second ceiling is local work, not permission to lengthen either request. Whether 5 seconds is enough for the broker is **DOCUMENTATION_VERIFICATION_REQUIRED**. These numbers must not be raised in a future patch without a new approval.

Cancellation before the first DNS call sends nothing. Cancellation after the first request has been written cannot pull that request back. The controller then skips request 2, closes the socket, discards the body, and writes no success file.

## Current code versus this specification

B2 can reject a bad description in memory. It cannot time out a connection, verify a certificate, or stop a hostname change, because it never connects. A future implementation must show those controls in tests before Gate 2 can be considered complete. Gate 2 still would not authorise an OANDA call.
