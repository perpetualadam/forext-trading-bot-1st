# Standalone historical frontend

```powershell
python -I -S -B data\research\trading_intelligence_v2\historical_session_entry.py
```

historical_session_entry.py loads only the isolated research package and delegates
to direct_history.launch. No arguments, account ID, token, .env reader, production
credential getter or R.56 permit is accepted. Current execution displays the exact
proposal and exits 2 with AUTHENTICATED_EXECUTION_DISABLED before any input or
worker. This stage creates no real grant and does not activate admission.

The future admitted run_approved_session uses the unchanged V2.6G admission gate,
then the distinct phrase CONFIRM ONE HISTORICAL EUR_USD REQUEST. The confirmation
screen is outside the timed acquisition. The existing supervisor reserves in the
protected archive before worker startup. After the worker's single-use claim,
TerminalCredentialProvider reads the token in memory and the same <=2048-byte pipe
delivers it to the existing worker, exact GET, validator and atomic publisher.

The original prompt functions are inseparable from R.56 grants. Reuse their
familiar hidden-input mechanism rather than invoking or modifying their gates:
the new provider uses the same Windows getwch primitive used by stdlib getpass,
with kbhit/deadline polling, backspace and Ctrl-C handling. It refuses redirected
streams and never falls back to echoed input. No token characters or stars print.
Header-safe token validation is at least as restrictive as the original prompt;
the provider has no token field, repr, persistence or arbitrary callback.

A narrow controller change accepts this one exact additional provider class only
after the unchanged admission check and passes its existing work deadline to the
prompt. No request/state/fencing rule changed. The **15-second total budget includes
native preparation, token entry, network, validation, publication and fencing**;
the token-entry window is therefore less than fourteen seconds. Timeout consumes
the reservation and fences the worker. No input thread, extra process or journal
was added. Actual input is Windows-native; tests use synthetic console objects.

Existing reuse: oanda_existing_readonly.candle_request; oneshot.run_once;
oneshot_network; oanda_history_manifest.validated/bars; oneshot_response.publish_candles;
oneshot_archive.Archive. The R.56 and V2.6G source gates remain byte-identical.
No new HTTP client, downloader, approval issuer or archive was added.

Research preparation: import_preview preserves original decimal strings in the
V2.3 SCHEMA and uses the existing normalized Bar adapter. It performs no replay,
CSV publication or rights/independence attestation. The V2.3 licensed-file importer
still refuses broker API URLs and requires all six instruments. Do not relabel an
OANDA response with a fake public URL to bypass it. Existing V2.6 broker-dataset
integration is the route for future adequately covered and permission-reviewed
OANDA datasets. Frozen V2.2–V2.5/profit-protection sources and thresholds are unchanged.

The first known interval is connectivity-only and previously examined, not new
independent strategy evidence. No evaluation was run. No bulk plan or acquisition
was triggered before the separately authorised first request succeeds; six-pair
12–24-month acquisition still needs its own data-use/retention review and approval.
