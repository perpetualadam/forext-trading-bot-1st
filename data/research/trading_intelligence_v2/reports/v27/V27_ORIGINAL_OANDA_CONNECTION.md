# Original connection audit — 2026-10-28

Baseline: main 99df373c6ef6b7c711670ef3369024c210747b29. The existing
scheduler/operator_attention.jsonl modification is unrelated and preserved.
R.56 was inspected as source only; its entry command was not run.

R.56 real_session_entry.reader prints the plan and uses input("Confirmation: ").
diagnostic_supervisor.run_real_session first checks the source gate, accepts
CONFIRM ONE DIAGNOSTIC SESSION, consumes the existing one-session activation,
then calls credential_ipc.prompt_account_id and prompt_hidden_token. Both prompt
functions check R.56 source/runtime grants before input; the latter uses
getpass.getpass("API token: ") and validates a 16–128-character token. Therefore
these functions cannot be called independently of their diagnostic grants.

Current live_session_gate.REAL_SESSION_SOURCE_ENABLEMENT is **False**. Neither
that constant, the R.56 permit nor its consumed marker was changed or recreated.
Permit/marker preservation was checked by existence, file identity, size and mtime
metadata; their contents were not read.

R.56 does not use the operational SDK client. The supervisor sends in-memory
credentials through bounded IPC to disposable workers. diagnostic_worker._step
uses RestrictedLiveTransport.get_account_summary/get_pricing; LiveExchange.exchange
constructs standard-library HTTPSConnection to api-fxtrade.oanda.com:443.
The exact plan is:

- GET /v3/accounts/{accountID}/summary
- GET /v3/accounts/{accountID}/pricing?instruments=EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF

No historical candle request is part of that diagnostic. Each HTTPS request has a
five-second timeout, with supervisor request/session caps of five/fifteen seconds.
Token prompts precede the timed dispatch loop. TLS validation, redirect/status/
body-size checks, JSON parsing and reduced diagnostics are in the restricted
transport/worker. The supervisor redacts and persists reduced diagnostic records,
cleans up children, expires capabilities and releases held credential references.
Python strings are not guaranteed securely erased. Source analysis found no
run_bot startup in this path; dynamically loaded dependencies are the R.56
diagnostic phases, not the operational trading loop. None were imported here.

The user's previous successful diagnostic is evidence of past repository access,
not verification of today's connectivity, historical route or account rights.
Weekend/stale-price history was not re-probed.

Operational history is forex_bot.oanda_client.fetch_ohlcv_range(:324): it calls
get_api, chunks from/to InstrumentsCandles GET requests, requests **mid only**,
uses _oanda_request retries and returns a provenance-bound DataFrame. It can be
called without run_bot, but its import loads Config/dotenv and its SDK can write.
It is unsuitable unchanged for the exact one-attempt MBA request. Its reviewed
non-account InstrumentsCandles contract is reused through candle_request/SPEC;
neither the operational client nor its credential storage is imported.

No broad replacement infrastructure was needed for this first request. Existing
one-shot transport, validation and protected archive were reused. The only
terminal correction is bounded native hidden input: ordinary getpass blocks and
can fall back to echo, so it cannot preserve the retained total deadline safely.
