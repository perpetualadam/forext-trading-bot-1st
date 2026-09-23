DEPLOYMENT STATUS:
SUCCESS

VALIDATION LEVEL:
2

DEPLOYMENT BOUNDARY UTC:
2026-09-22T22:28:31Z (container start; BOT STARTED 22:28:34Z)

DEPLOYMENT BOUNDARY LOCAL:
2026-09-22 23:28:31 BST (BOT STARTED 23:28:34 BST)

NEW CONTAINER:
8fe23812384e39439aff7779c0245751d32af2c173dcddb4cf2fedeb00723388 (forexttradingbot1st-bot-1)

NEW IMAGE:
df7ddcdf2744 (sha256:df7ddcdf27445f2b196d1afc17db7b0e9987db1f4cc28196b44de036a2f3066b)

NEW BUILD CONFIRMED:
YES

STARTUP HEALTHY:
YES

OPEN POSITIONS AT RESTART:
0 broker / 0 local (see section 2 — two old-build positions closed at 22:26Z, before compose down)

RECONCILIATION HEALTHY:
YES

POSTDEPLOY ENTRY CANDIDATES OBSERVED:
0

POSITIVE-CLEARANCE CANDIDATES:
0

INSUFFICIENT-CLEARANCE CANDIDATES:
0

INSUFFICIENT-CLEARANCE SKIPS:
0

ORDERCREATE SENT DESPITE NONPOSITIVE CLEARANCE:
0

SUCCESSFUL FILLS:
0

FILL-BASED R:
n/a

STOP_LOSS_ON_FILL_LOSS CANCELS:
0 (post-boundary)

PRECHECK-INVALID CANCELS:
0

POSITIVE-CLEARANCE RESIDUAL-RACE CANCELS:
0

OLD "MISSING ORDERFILLTRANSACTION" MESSAGE COUNT:
0 (post-boundary)

EXPLICIT CANCEL CLASSIFICATION OBSERVED:
NOT YET EXERCISED

BLIND ORDERCREATE RETRIES:
NO

GHOST BROKER POSITIONS:
0

GHOST LOCAL POSITIONS:
0

NEW-BUILD BOT POSITIONCLOSE 45–90 SEC:
0

BROKER EXIT ACCOUNTING HEALTHY:
NOT EXERCISED

HEADROOM GUARD PRODUCTION-VALIDATED:
PENDING NATURAL EVENT

ALLOW PATH PRODUCTION-VALIDATED:
PENDING NATURAL EVENT

CANCEL CLASSIFIER PRODUCTION-VALIDATED:
PENDING NATURAL EVENT

CODE CHANGED DURING DEPLOYMENT:
NO

ENV CHANGED:
NO

DOCKER REBUILT:
YES

DOCKER RESTARTED:
YES

MANUAL OANDA ORDERS:
NO

MANUAL OANDA CLOSES:
NO

## 1. Deployment boundary

All post-deploy evidence is after **2026-09-22T22:28:31Z / 23:28:31 BST**.

| Item | Value |
|---|---|
| Workspace git HEAD | `a9f0e2a` (ClientPrice freshness commit) |
| Implementation files | uncommitted working-tree copies of `entry_geometry.py`, `oanda_exec.py`, `bot_loop.py` — these were copied into the image |
| Image | `forexttradingbot1st-bot:latest` `df7ddcdf2744` created at deploy |
| Final bot container | `8fe23812384e…` created 22:28:25Z, started 22:28:31Z |
| Final db container | `f5b3a90bc0ce…` postgres:16-alpine, same `forexttradingbot1st_pgdata` volume |
| BOT STARTED | 23:28:34.714779 BST / 22:28:34Z |
| Health `started_at` | 2026-09-22T23:28:34.709653+01:00 |

Container file proof of the new build (not the 12-hour-old image `1452ebf3eb3f`):

- `/app/forex_bot/entry_geometry.py` contains `insufficient_sl_trigger_clearance`
- `/app/forex_bot/oanda_exec.py` contains `OUTCOME_CANCELLED`
- `/app/forex_bot/bot_loop.py` contains `OrderCreateCancelled`

OANDA lastTransactionID at validation time: **3241**. Last broker write was 22:26:26Z (pre-boundary). No post-boundary MARKET_ORDER.

## 2. Pre-deployment safety state

Recorded ~22:26:08Z / 23:26:08 BST, before compose down.

| Item | Value |
|---|---|
| Old container | `b6f93ceb6011…` created 22:10:22Z, up ~12h |
| Old image | `1452ebf3eb3f` |
| Old BOT STARTED | 2026-09-22T11:22:39+01:00 |
| Mode | `EXECUTION_MODE=live_broker`, `TRADING_MODE=live`, host `api-fxtrade.oanda.com` / fxTrade |
| Symbols | EUR_USD, GBP_USD, USD_JPY, AUD_USD, USD_CAD, USD_CHF |
| ATR | `USE_ATR_STOPS=true`, `SL_ATR_MULT=2.0` |
| Reconcile | last_success true, mismatch 0, `broker_positions_fetched=2`, `broker_pending_orders=4`, `open_positions_count=2` |
| Import / auto_fix | `RECONCILE_IMPORT_BROKER_POSITIONS=true`, `RECONCILE_ACTION=auto_fix` |

The two local/broker positions at first inspect were the pre-boundary fills:

- USD_CAD SELL `3223` / `cid-c3925cae…` opened 22:06:11Z, SL `3225` + TP `3224`
- USD_JPY BUY `3227` / `cid-2ccd9dde…` opened 22:20:26Z, SL `3229` + TP `3228`

Four pending orders = broker-attached SL/TP. Restart with protected positions is supported by existing import/reconcile. No flatten was performed.

Read-only OANDA history shows those two trades were already closed **before** `docker compose down` (22:27:02Z):

| Time UTC | Tx | Event |
|---|---|---|
| 22:26:12 | 3234/3235 | USD_CAD `TRADE_CLOSE` of 3223 (old-build PositionClose) |
| 22:26:26 | 3238/3239 | USD_JPY `TRADE_CLOSE` of 3227 (old-build PositionClose) |

Those closes are **OLD BUILD**, ~20 min and ~6 min after entry, not 45–90s, and not caused by this deployment. At new-container start the broker book was already flat.

## 3. Docker deployment evidence

Established procedure used: `docker compose down` then `docker compose up -d --build`. `.env` and compose file were not edited.

Sequence:

1. **22:27:02Z** compose down — old bot/db removed; `pgdata` volume kept.
2. First `--build` failed on a Docker Desktop snapshot error (`parent snapshot … does not exist`). No code change.
3. Immediate retry of the same `up -d --build` **succeeded**; image `df7ddcdf2744` produced; containers started (~22:27:21Z).
4. Those first new containers then disappeared from `docker ps` (empty compose project) within ~1 minute. Cause not determined (Docker Desktop / host). Image remained.
5. **22:28:24Z** `docker compose up -d` **without rebuild** started the same already-built image. This is the live stack.

No strategy/env/code edits. No manual OANDA writes.

## 4. Startup / reconciliation evidence

BOT STARTED line:

```
BOT STARTED | host=live exec=live_broker broker_orders=True paper=False | symbols=['EUR_USD', 'GBP_USD', 'USD_JPY', 'AUD_USD', 'USD_CAD', 'USD_CHF'] | … EUR_USD=IN GBP_USD=IN USD_JPY=IN AUD_USD=IN USD_CAD=IN USD_CHF=IN
```

Then: Application startup complete; Uvicorn on :8000; `GET /health` 200; bot=`running`; `trading_allowed=true`.

`/system` after first cycles (~23:29–23:31 BST):

- `last_success=true`, `last_error=null`, `mismatch_count=0`
- `broker_positions_fetched=0`, `broker_pending_orders=0`
- `open_positions_count=0`
- `pre_trade_entry_allowed=true`
- `last_bot_cycle_utc` advancing (23:29:36, later 23:31:38)
- Independent read-only `fetch_broker_positions_detail()`: empty
- AccountDetails GET succeeded (`lastTransactionID=3241`, NAV 97.2430)
- No startup traceback, no crash loop, no CONFLICT/IMPORT anomaly
- In-process fill counters reset to 0 (new process); DB still has historical `exec_orders` (526 rows), none created after 22:27Z

## 5. Post-deployment entry candidates

0 observed.

Evidence: no new `exec_orders` after 22:27Z; OANDA last_id unchanged at 3241; new-container logs have no `[ENTRY GEOMETRY]`, no `insufficient_sl_trigger_clearance`, no `BROKER_FILL`.

Evaluate cycles are running. No candidate reached the live PricingInfo / OrderCreate path during this observation window. No signal was injected.

## 6. Trigger-side clearance evidence

None in production yet. The guard is present in the running image; it has not been exercised by a natural candidate.

## 7. Invalid-clearance skip evidence

Not observed. OrderCreate despite nonpositive clearance: **0** (no OrderCreate at all after the boundary).

## 8. Positive-clearance allow evidence

Not observed.

## 9. Successful fill geometry

0 post-deploy fills. ATR/TP/2R/sizing not re-measured on a live fill. Container env still `USE_ATR_STOPS=true`, `SL_ATR_MULT=2.0`.

## 10. OANDA cancellation classification

No post-boundary `orderCancelTransaction`. Classifier is in the image; **not yet exercised** in production.

## 11. STOP_LOSS_ON_FILL_LOSS analysis

Post-boundary count: **0**.

Pre-boundary (old build, not this validation): 3201/3203/3213 were `STOP_LOSS_ON_FILL_LOSS` before 22:00Z. Do not mix with the new build.

The quote→OrderCreate race is **not** claimed eliminated.

## 12. Retry safety

No post-boundary OrderCreate, so no retry population. `last_id` 3241 → 3241. **BLIND ORDERCREATE RETRIES: NO.**

## 13. Ghost-state check

Broker open 0, local open 0, pending 0, mismatch 0. No broker-open/local-missing or local-open/broker-flat. No unexpected IMPORT/CONFLICT after start.

## 14. Existing-position management

No open live position after the boundary, so closeoutBid/Ask management was not exercised on the new build. Not reopened.

## 15. Broker-exit accounting

No post-deploy SL/TP exit. NOT EXERCISED.

Pre-boundary TRADE_CLOSE 3231/3235/3239 belong to the old process.

## 16. Risk-guard observations

USD-direction and notional caps were not newly tripped after deploy (no entries). Env still live_broker with the same six symbols. Not forced.

## 17. Remaining unexercised behavior

- insufficient_sl_trigger_clearance skip before OrderCreate
- positive-clearance allow → OrderCreate
- fill-based ~2R
- `[ORDER CANCEL]` / STOP_LOSS_ON_FILL_LOSS classification
- residual quote→order race
- live management closeout side
- broker-exit booking
- new-build 45–90s PositionClose watch (0 so far; no entries)

## 18. Final validation level

**LEVEL 2 — STARTUP VALIDATED**

LEVEL 1: new image/container running — proven.  
LEVEL 2: normal startup, OANDA GET, DB, reconcile clean, six symbols, no crash/ghost/retry — proven.  
LEVEL 3–5: require natural entry/cancel events that have not occurred yet.

DEPLOYED SUCCESSFULLY. LIVE BEHAVIOR VALIDATION PENDING NATURAL EVENTS.

CODE CHANGED DURING DEPLOYMENT: NO  
ENV CHANGED: NO  
MANUAL OANDA ORDERS: NO  
MANUAL OANDA CLOSES: NO
