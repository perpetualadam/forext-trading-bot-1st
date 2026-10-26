# TLS, method, endpoint, and redirect evidence

The offline tests call the adapter while DNS lookup, connection open, and `HTTPSConnection` construction raise if touched.

| Control | Observed result |
| --- | --- |
| Host | Both injected calls receive `api-fxtrade.oanda.com`. Any other host raises `R51_REJECTED` before the factory. |
| TLS | Each call receives a real default context with `CERT_REQUIRED` and hostname checking enabled. |
| Method | Both calls are GET. POST raises before the factory. |
| Templates | Call order is instruments, then pricing. An orders path raises before the factory. |
| Instrument filter | Both targets contain the six names and no others. |
| Home conversions | `includeHomeConversions=true` is present only on the pricing target. |
| Timeout | Both calls receive 5.0 seconds. A 30-second value raises before the factory. |
| Redirects | Status 302 stops after one call. The body is not read. |
| Retries | A factory exception stops after one attempt. |
| Body | The recorded body is empty. A prepared body raises before the factory. |
| Streaming | A stream flag raises before the factory. |
| Call cap | The session completes two calls. A third call raises and the factory is not contacted again. |
| Concurrency | The fake connection rejects a re-entered call. The process thread count does not rise. |

`disabled_preview` reports `NETWORK_DISABLED` and `live_entry_point: NOT_IMPLEMENTED`.
