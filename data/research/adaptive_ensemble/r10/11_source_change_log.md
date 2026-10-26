# Source change log

## forex_bot/app.py

CODE MODIFIED. Pre-stage sha256 `3ff01244ed217e85d211bec819a7ebff9c96fb0412c56e5a768792ab54b31ca1`. Post-stage sha256 `7a925e3f5a247b9f92ab42db17242c5a895de099b6897145fba6bfb7d737ef9e`.

The existing blocker was that startup lived only inside lifespan and imported the broker SDK, trading metrics, and `run_bot` at module import. The smallest seam is `initialise_application`. Broker and `run_bot` imports are now inside the production functions that need them. `import forex_bot.app` no longer imports `oandapyV20`.

Production lifespan still calls the seam with production ports. Those ports still connect, build the broker, and start `run_bot` when lifespan actually runs. Tests never call them. One added production check refuses an empty symbol list before persistence. Account-summary and reconciliation failures on the production port still warn and continue.

`trading_ready` is false even on the production branch. Offline ready is a separate flag.

## Unchanged application files

`forex_bot/bot_loop.py`, `forex_bot/database.py`, and `forex_bot/orders.py` keep their stage-start hashes. No edit was required in those files. Protected files (`telegram_control.py`, `live_safety.py`, `strategy_meta.py`, `oanda_exec.py`, requirements, Docker files) keep their expected hashes.

## Existing tests

`tests/test_r8_reservation_safety.py` now pins the post-stage `app.py` hash. The reservation assertions are unchanged.

`tests/test_r9_position_safety.py` pins the same hash. Its socket and DNS assertions now match `NETWORK_BLOCKED` and `DNS_BLOCKED`. The barrier still raises. The R.9 safety assertions are unchanged.

## New files

- `tests/r10_fakes.py`
- `tests/test_r10_offline_startup.py`
- `data/research/adaptive_ensemble/r10/20_run_offline_tests.py`

The cumulative `git diff --stat` against HEAD for `app.py`, `bot_loop.py`, `database.py`, and `orders.py` is 1444 insertions and 208 deletions. That figure includes earlier uncommitted work. It is not an R.10-only diff. R.10 did not change `bot_loop.py`, `database.py`, or `orders.py`.
