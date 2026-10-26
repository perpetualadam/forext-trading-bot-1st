# R.56 phase 2 safety review

## Isolation demonstrated

The implementation files import only the Python standard library. `test_phase2_offline.py` parses those files with `ast` and rejects imports of `forex_bot`, `oandapyV20`, `requests`, `urllib`, `http`, `socket`, `ssl`, and `main`. A second check rejects import names `bot_loop`, `oanda_exec`, `oanda_client`, `trading`, `execution`, and `app`.

The test process replaces `socket.socket`, `socket.create_connection`, and `socket.getaddrinfo` before loading the logger. The DNS call raises `network_blocked`. After the load, no `r56p2_` module name is a `forex_bot` or `oandapy` module. `forex_bot.oanda_client`, `forex_bot.config`, and `forex_bot.oanda_exec` were not in `sys.modules`.

There is no function that builds an HTTP request, an order body, or a position close. Sizing output sets `executable_order` and `order_payload` to `NOT_PRODUCED`. Extra keys named `order` or `type` are dropped.

## Credential and identity handling

- No `.env` read and no credential prompt.
- `launch` rejects `--live`, `--connect`, `--authenticate`, `--account`, unknown flags, and positional arguments with exit code 2 before any file is written.
- Account `id` and `alias` are sensitive keys. Their values must not appear in the JSON.
- A bearer value or a string containing `SYNTHETIC-TOKEN` is a sensitive literal. If it would be written, the record is replaced by `SENSITIVE_OUTPUT_BLOCKED`.
- `write_exception` accepts an exception object and does not stringify it. The fixed code is `EXCEPTION_CONTAINED`.
- Session ids are random `r56-` hex values. An id that does not match that shape is rejected.

## Log location

Writes are accepted only under `phase2_offline/synthetic_logs`. A path outside that directory raises `DiagnosticPathRejected` with `LOG_PATH_OUTSIDE`. File names are `r56-diag-<session><kind><number>.json`, created with exclusive create, so a repeat does not replace an existing diagnostic file or an unrelated file in that directory.

## What this does not prove

`DATA_ONLY_MODE_NOT_PROVEN_SAFE` still applies to the production process. This logger is safe because it is a different program with no call into the trading process. It does not make `main.py`, `paper_broker`, or `live_broker` safe. A variable named dry-run is not used as evidence.

The production client object returned by `build_api` can be used for reads and, by `oanda_exec.py`, for account-changing calls. This phase does not import that client, so it does not create a guarded live session.
