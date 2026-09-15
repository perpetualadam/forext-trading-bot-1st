# Forex trading bot

**Yes — this bot executes real trades.** It is not a paper-only simulator.

With `EXECUTION_MODE=paper_broker` or `live_broker`, a passed signal inside the `LIVE_*` window sends official OANDA v20 market orders (`MarketOrderRequest`, FOK, OPEN_ONLY, optional SL/TP on fill) and closes (`PUT .../positions/{instrument}/close`). Live-tagged positions are always closed at the broker (fail closed if orders are off).

It does **not** send orders when `EXECUTION_MODE=paper` (the `.env.example` default) or when you are outside the live window (`window_paper` simulated fills). `TRADING_MODE=live` alone only selects `api-fxtrade.oanda.com`; it does not place orders.

## What actually places orders

Two switches, not one:

| Setting | What it does |
|---|---|
| `TRADING_MODE=practice` / `live` | OANDA **host + token type** (`api-fxpractice` vs `api-fxtrade`). Does **not** by itself place or block orders. |
| `EXECUTION_MODE=paper` / `paper_broker` / `live_broker` | **Fills.** `paper` never sends orders. `paper_broker` / `live_broker` send real broker orders. |

If `EXECUTION_MODE` is unset, `PAPER_TRADING` + `TRADING_MODE` derive the same three modes. `USE_OANDA_LIVE` is only used when `EXECUTION_MODE` is unset.

**NAV in the logs is not a fill.** Every cycle calls AccountSummary so sizing and the notional cap use real equity. An exposure check can run and skip the open (`Skip open — notional cap`) with **no** OrderCreate.

Inside `LIVE_*` hours (local to `LIVE_TIMEZONE`, e.g. 13:00–17:00 UK) with broker execution on, a passed signal **must** get a broker fill or the bot skips (fail closed). It will not invent a local “live” fill.

## Capital first

Two separate controls:

| Setting | What it does |
|---|---|
| `POSITION_NOTIONAL_PCT_OF_NAV` | **Per-trade** face value. `0.02` ≈ 2% of broker NAV, floored to whole OANDA units. Not stop-loss risk. |
| `MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV` | **Book** cap: max total gross USD notional = NAV (in USD) × this fraction. |

If the portfolio setting is unset, it **inherits** `POSITION_NOTIONAL_PCT_OF_NAV` (the previous 2% book cap). A 1-unit order that would push the book over the cap is still rejected. If size rounds below 1 unit, the bot skips rather than rounding up.

Stop-loss book risk is a third control: `MAX_PORTFOLIO_RISK_PCT`.

## Enable real execution

Copy `.env.example` to `.env`, then set one of these. The template starts in `paper` so a first `docker compose up` does not trade until you opt in.

**Practice account (real orders on fxPractice):**

```env
TRADING_MODE=practice
EXECUTION_MODE=paper_broker
USE_OANDA_LIVE=true
PAPER_TRADING=false
OANDA_ACCESS_TOKEN=...
OANDA_ACCOUNT_ID=001-...
LIVE_TIMEZONE=auto
TZ=Europe/London
LIVE_EUR_USD_START=13:00
LIVE_EUR_USD_END=17:00
POSITION_NOTIONAL_PCT_OF_NAV=0.02
MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV=0.06
```

**Live account (real money on fxTrade):**

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
MAX_PORTFOLIO_GROSS_NOTIONAL_PCT_OF_NAV=0.06
```

Confirm on `GET /system`: `execution_mode` is `paper_broker` or `live_broker`, `broker_orders_enabled=true`, `effective_paper_trading=false`. Logs should show `[ORDER SENT]` / `[EXECUTION] BROKER_FILL` when a trade opens.

See [DEPLOYMENT.md](DEPLOYMENT.md) for Docker.
