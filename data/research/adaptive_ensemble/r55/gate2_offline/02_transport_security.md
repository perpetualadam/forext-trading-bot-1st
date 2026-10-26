# Transport security

The transport accepts an already validated description, checks the TLS context, and only then calls the offline factory. A bad host, port, method, query, body, stream, retry, redirect flag, or path never constructs a double.

| Control | Offline result |
| --- | --- |
| Host `api-fxtrade.oanda.com` and port 443 | Mismatches raise before the factory. The double is given those constants, not a caller URL. |
| GET only | POST, PUT, PATCH, and DELETE raise before the factory. |
| Option A paths | Instruments then pricing. Summary, orders, trades, positions, transactions, and candles raise before the factory. |
| Query allowlist | Instruments: `instruments` only. Pricing: `instruments` and `includeHomeConversions=true`. The six names stay in fixed order. |
| No body, stream, retry, or redirect | Overrides raise before the factory. Status 301, 302, 303, 307, and 308 do not read a body and do not open another host. |
| Two requests | The controller plans two descriptions. A third prepared double is not constructed. |
| 1 MiB cap | Byte 1,048,577 is `RESPONSE_TOO_LARGE`. Those bytes are not stored in the result. |
| TLS | `verify_mode` must be `CERT_REQUIRED` and `check_hostname` must be true. Weaker contexts raise before the factory. `ssl.create_default_context()` meets that check and was not used to connect. |
| Token on the wire | A Bearer header is assembled only long enough to set a boolean. The double receives `authorization_present=True` and does not receive the token. |
| Errors | Exception text is a fixed code. Reader exceptions are replaced with `R55G2_REJECTED`. |
| Live socket | `sealed_live_factory` raises `R55G2_LIVE_TRANSPORT_NOT_ACTIVATED`. No `getaddrinfo`, `create_connection`, or `HTTPSConnection` call is present. |

HTTP 401, 403, 404, 429, and 5xx stop the session without decoding the body. A 429 is one attempt.

The account identifier is inserted into the in-memory path given to the test double. The evidence file is refused if that identifier, the synthetic token, `Bearer`, `Authorization`, a URL, `ACCOUNT_VERIFIED`, or `1.35` appears in it.

A GET-only client does not make the token read-only. Token permission in every successful document is `UNKNOWN`.
