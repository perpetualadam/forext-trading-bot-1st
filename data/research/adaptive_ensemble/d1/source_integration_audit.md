# Source integration audit

Method: AST parse of the 60 allowlisted Python files, plus reading of startup, safety, database, and strategy modules. The application was not imported. No service was contacted.

## Allowlisted import graph

`STATIC_INTEGRATION_PASS` for local imports inside the 60 allowlisted Python files. Every `forex_bot` import resolved to a module that is also on the allowlist. This does not prove runtime behavior.

`forex_bot/research`, `forex_bot/shadow`, and `forex_bot/decision_quality` are not on the repaired COPY list. The allowlisted modules do not import them. `v2_shadow/score_offline.py` and `v2_shadow/isolation.py` are also omitted, and the packaged modules do not import them.

## Components

- Entry point: `STATIC_INTEGRATION_CONCERNS`. Dockerfile and the G.12 inspect record both name `uvicorn forex_bot.app:app`. `app.py` matches the historical image sample. The rest of the process does not.
- Strategy registry: `STATIC_INTEGRATION_CONCERNS`. `strategy_meta.Strategy` sets `active = True` at construction. `initialise_fail_closed` later overwrites that from the durable file. A path that trades before that call would see the default. The lifespan calls initialise first. That order was not executed.
- Strategy dispatch: `STATIC_INTEGRATION_BLOCKED_BY_MISSING_EVIDENCE` for the image. Current `bot_loop.py` is not the image sample.
- Risk management: `STATIC_INTEGRATION_CONCERNS`. `execution.pre_trade_entry_blocked_reason` calls `live_open_blocked_reason`. `live_manage.py` differs from the image sample.
- Order router: `STATIC_INTEGRATION_CONCERNS`. `oanda_exec.py` differs from the image sample. Close actions are not gated by `assert_new_live_exposure_allowed`.
- Live-order gate: `STATIC_INTEGRATION_PASS` as a static rule in the current and image-matching `live_safety.py`: effective state is set BLOCKED on process start. Enforcement through every order call was not executed.
- Scheduler: `STATIC_INTEGRATION_CONCERNS`. `run_bot` loops forever and calls account summary, pricing, the symbol cycle, and `evolve`.
- Database: `STATIC_INTEGRATION_CONCERNS`. `get_connection` runs DDL on first use. Called unconditionally from lifespan.
- Shadow imports: `STATIC_INTEGRATION_CONCERNS`. Current `bot_loop.py` imports `v2_shadow`. The image copy of `bot_loop.py` is different, so the deployed import is unknown.
- Feature flags: `STATIC_INTEGRATION_BLOCKED_BY_MISSING_EVIDENCE`. Compose interpolates `TRADING_MODE`, `EXECUTION_MODE`, `PAPER_TRADING`, and `KILL_SWITCH`. The live values were not read.
- Startup and shutdown: `STATIC_INTEGRATION_CONCERNS`. See the startup audit. Shutdown cancels tasks and sends a stop alert. It does not flatten positions in the lifespan block that was read.
- Dependencies: `STATIC_INTEGRATION_CONCERNS`. Requirements are minimums. Third-party imports such as `oandapyV20`, `fastapi`, and `psycopg2` are declared, not locked.
- Packaging paths: `STATIC_INTEGRATION_PASS` for the repaired Dockerfile against the 63-file staging set. `STATIC_INTEGRATION_CONCERNS` for deployment, because the historical image used a broad `COPY forex_bot ./forex_bot`.

No circular import was observed in the AST walk. A circular import can still exist through runtime `import` inside functions. That was not executed.

Static inspection does not verify runtime integration.
