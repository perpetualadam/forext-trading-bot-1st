# Read-only adapter integration

`oanda_existing_readonly.py::candle_request` returns a defensive copy of the
existing `oneshot.SPEC` and requires the unchanged exact request guard. The SDK
instrument path, parameter names, MBA components and RFC3339 wire convention
are retained. Both temporal bounds replace the operational latest-call count;
the ranged client's chunking, six-attempt wrapper and permissive frame parsing
are not used.

Execution path used by tests:

1. `run_synthetic_session` delegates to the existing `run_https_fixture`.
2. The unchanged `oneshot.run_once` supervisor starts the same fenced worker.
3. The worker reserves the existing durable grant before credential delivery.
4. Its HTTPS branch calls `fetch_synthetic_candles` with the adapter's schema.
5. `fetch_https_fixture` independently copies and revalidates that schema, then
   uses the existing `CandleTransport(attempts=1)` and `_exchange_get`.
6. Existing validation, atomic archive publication, hashes and completion run.

No controller, reservation, IPC, archive or Windows fencing implementation was
replaced. No new journal, transport implementation, network factory, redirect,
fallback, retry, pagination or reauthorisation was introduced.

The logical host is fixed to `api-fxtrade.oanda.com`; physical test connections
remain IPv4 loopback at the validated fixture port, with certificate and hostname
verification. The worker's socket policy is unchanged. Default V2.6D tests retain
their original read policy. Only explicit V2.6E test mode additionally permits
reading three fixed source files as text for AST compatibility checks; operational
imports and private-state reads remain blocked.

Native verification used the existing protected
`C:\TradingResearchData\OANDA` binding and dedicated synthetic namespace. Owner
and SYSTEM ACL requirements, NTFS, held directory identities, junction/reparse
refusal, hardlink checks, immutable publication and hash checks passed unchanged.
The existing binding's timestamp remained 2026-10-27; no rebind, root ACL change,
OneDrive/Git fallback, live data publication or credential publication occurred.
