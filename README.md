# Forex trading bot

OANDA v20 bot with a **capital-first** live path: size and cap from broker NAV, then place real market orders only inside the configured live window.

## What actually places orders

Two switches, not one:

| Setting | What it does |
|---|---|
| `TRADING_MODE=practice` / `live` | OANDA **host + token type** (`api-fxpractice` vs `api-fxtrade`). Does **not** by itself place or block orders. |
| `EXECUTION_MODE=paper` / `paper_broker` / `live_broker` | **Fills.** `paper` never sends orders. `paper_broker` / `live_broker` send official `MarketOrderRequest` (FOK, OPEN_ONLY, SL/TP on fill) and `PositionClose`. |

If `EXECUTION_MODE` is unset, `PAPER_TRADING` + `TRADING_MODE` derive the same three modes. `USE_OANDA_LIVE` is only used when `EXECUTION_MODE` is unset.

**NAV in the logs is not a fill.** Every cycle calls AccountSummary so sizing and the notional cap use real equity. An exposure check can run and skip the open (`Skip open — notional cap`) with **no** OrderCreate.

Inside `LIVE_*` hours (local to `LIVE_TIMEZONE`, e.g. 13:00–17:00 UK) with `EXECUTION_MODE=live_broker`, a passed signal **must** get a broker fill or the bot skips (fail closed). It will not invent a local “live” fill. Outside the window it uses `window_paper` (simulated fills, no broker orders).

## Capital first

When `POSITION_NOTIONAL_PCT_OF_NAV=0.02`, each new position is about **2% of broker NAV** (floored to whole OANDA units). The same fraction caps total gross USD notional. If that rounds below 1 unit, the bot skips rather than rounding up.

## Live checklist

```env
TRADING_MODE=live
EXECUTION_MODE=live_broker
USE_OANDA_LIVE=true
PAPER_TRADING=false
OANDA_ACCESS_TOKEN=...
OANDA_ACCOUNT_ID=001-...
LIVE_TIMEZONE=auto
TZ=Europe/London
LIVE_EUR_USD_START=13:00
LIVE_EUR_USD_END=17:00
POSITION_NOTIONAL_PCT_OF_NAV=0.02
```

Confirm on `GET /system`: `execution_mode=live_broker`, `broker_orders_enabled=true`, `effective_paper_trading=false`. Logs should show `[ORDER SENT]` / `[EXECUTION] BROKER_FILL` when a trade opens.

See [DEPLOYMENT.md](DEPLOYMENT.md) for Docker.
