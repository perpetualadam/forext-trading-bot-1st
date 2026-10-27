# Next step — review only

Offline bridge verification is complete; do not execute an OANDA request.
Normal acquisition remains AUTHENTICATED_EXECUTION_DISABLED. No live flag or
operator-facing bypass is supplied.

Before one separately authorised read-only LIVE request:

1. Obtain authoritative current endpoint support and applicable OEL usage/retention
   evidence, including treatment of derived publication. Provider questions are
   prepared but unsent.
2. Review a future native session/grant and credential-delivery change. It must
   preserve the existing one-shot journal, durable reservation, process fence,
   one-attempt exchange, exact scope and protected archive; this stage creates
   no real grant writer and exposes no authenticated execution entry point.
3. Separately approve one exact historical session, including any provider-required
   interval revision, after reviewing the evidence. Never infer approval from
   successful localhost TLS, a synthetic grant or a documentation status flag.

Unapproved specification remains LIVE, host `api-fxtrade.oanda.com`, GET
`/v3/instruments/EUR_USD/candles`, M5, MBA, smooth=false, includeFirst=true,
from `2026-09-02T10:00:00Z` to `2026-09-02T10:49:59Z`, count omitted.
Do not assume ten candles. Boundary ambiguity remains; validate actual completed
MBA starts/count/gaps without filling missing rows or silently changing endpoints.

No R.87 recovery, R.88, strategy/sizing/SL/TP changes or production integration.
Stop after V2.6D. **Production trading remains NO-GO.**
