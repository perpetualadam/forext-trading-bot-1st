# Old one-minute bug recurrence test (new management build)

NEW-BUILD BOT-INITIATED ~45-90 SECOND CLOSES:
0

USER/MANUAL ~45-90 SECOND CLOSES:
0

UNKNOWN ~45-90 SECOND CLOSES:
0

OLD ONE-MINUTE BUG RECURRED:
NO

CONFIDENCE:
HIGH

WINDOW:
New-build entries at or after 2026-09-21T09:40:11Z through lastTransactionID 2504 (includes POST-23:00 deploy at 22:00:04Z).

---

## Rule

An event counts as recurrence **only** with positive evidence that the **new** bot issued `PositionClose` on the live management path (evaluate → profit-protection / local SL-TP / weekend flatten → `oanda_exec` PositionClose) **and** hold is 45–90s.

Not recurrence:

- user/manual `TRADE_CLOSE`
- broker `STOP_LOSS_ORDER` / `TAKE_PROFIT_ORDER`
- unattributed `MARKET_ORDER_POSITION_CLOSEOUT` (no PG `exit_reason`, no `[BROKER_CLOSE]` / `[ORDER CLOSE]`)

## New-build completed exits in band

52 new-build exits. Two fall in 45–90s; both are broker stops:

| trade | pair | hold | reason | class | recurrence? |
|---|---|---:|---|---|---|
| 2420 | EUR_USD | 49.0s | `STOP_LOSS_ORDER` | BROKER_STOP_LOSS | NO |
| 2430 | USD_JPY | 68.8s | `STOP_LOSS_ORDER` | BROKER_STOP_LOSS | NO |

## Proven new-bot PositionClose (for scale)

11 fills with PG `profit_protection` and/or `[BROKER_CLOSE] … (PositionClose)`:

| trade | hold | evidence |
|---|---:|---|
| 2129, 2143, 2213, 2223, 2251, 2297, 2301, 2317, 2357, 2361 | 1159–12809s | PG `profit_protection` |
| 2494 USD_JPY | **427.8s** | log `BROKER_CLOSE … source=OANDA_CURRENT (PositionClose)` at 22:15:31Z; PG `profit_protection` |

Shortest proven new-bot PositionClose is **2494 at 7.1 minutes**, not ~61s.

## Manuals in new-build (none in band)

2181 (895s), 2155 (5541s), 2454 (1915s), 2470 (575s) — all `TRADE_CLOSE` flatten/manual.

## UNKNOWN

No new-build `POSITION_CLOSEOUT` in 45–90s. Old-build 2101 (88s, no PG) is outside this test.

## Why NO, not INCONCLUSIVE

INCONCLUSIVE would require an unattributed new-build 45–90s PositionClose. That set is empty. The band contains only two broker stops. The new bot has issued PositionClose and those holds are ≥428s.

PRODUCTION CHANGES MADE: NO  
OANDA WRITES PERFORMED: NO  
DOCKER RESTARTED: NO
