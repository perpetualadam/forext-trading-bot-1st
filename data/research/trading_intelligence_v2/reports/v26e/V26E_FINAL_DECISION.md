# V2.6E final decision — 2026-10-28

`TIV26E_READ_ONLY_INTEGRATION_VERIFIED`

This classification covers the existing-client request contract and the
synthetic one-shot integration. Authenticated execution remains disabled.
Production trading remains **NO-GO**. No real OANDA request was sent.

Actual baseline: `6a3a1811b477f474e5de4c1f870cc5ac54657f57`, branch `main`,
initially clean. The supplied `ebbae93` baseline is historical and was not reset.

The existing SDK candle contract is non-account `InstrumentsCandles`. The new
thin adapter reuses the exact V2.6D request and transport, durable controller,
credential IPC, disposable worker, response validator and protected archive.
No second downloader, engine, journal, live credential loader or host was added.

Answers:

- Existing configuration can be reused as a reviewed schema and configuration-key
  contract without importing trading execution. The operational configuration
  itself cannot be imported in this stage: it reads dotenv and credential values.
- The bot's latest and ranged candle calls use the non-account route. Its pricing
  snapshot is account-specific; those are different contracts.
- The research controller now runs the read-only adapter's exact schema through
  the real synthetic HTTPS worker path. All 50 V2.6E cases pass in portable
  Windows, protected native Windows storage and Linux modes.
- A future read-only request can be independent of trading. The current entry
  still refuses before provider access, and the worker permits only fixture
  loopback sockets. This stage creates no executable LIVE grant or credential
  loader.
- Before one real request: establish applicable endpoint/entitlement and data-use
  permissions, separately review the memory-only real provider and narrowly
  bound LIVE worker/grant activation, recheck archive binding, then obtain an
  explicit single-attempt approval for the exact proposal.

Current LIVE connectivity was not tested. Usage/retention permission is not fully
established. The separately reviewed proposal is in
[V26E_FIRST_REQUEST_APPROVAL.md](V26E_FIRST_REQUEST_APPROVAL.md); nothing in these
reports authorises execution. Stop after V2.6E.
