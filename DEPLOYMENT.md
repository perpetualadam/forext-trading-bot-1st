# Deployment (Docker / Compose)

## Feature parity vs. the original script

| Feature | Included? | Notes |
|--------|-----------|--------|
| Live / practice OANDA toggle | Yes | `TRADING_MODE` + `POST /set_mode`. Affects **which OANDA API host** is used for **candles**. |
| AI ensemble (local / external) | Yes | Default **LocalLLM** is a deterministic **quant stub** (MA trend + momentum + ATR); real providers use API keys. `ExternalLLMAPI` exists but is not registered by default. |
| Indicators (MA, RSI, MACD, BB, ATR) | Yes | ATR uses true range + rolling mean (more standard than the original shortcut). |
| BUY / SELL | Yes | Ensemble returns a direction (quant stub uses `ma_fast` vs `ma_slow`); RL can override with SKIP. |
| Session windows, pre-close sizing, volatility filter | Yes | Session times are interpreted in **UTC** (see limitations below). |
| Telegram + Discord alerts | Yes | Only sends if env vars are set. |
| PostgreSQL trade log | Yes | Lazy connect; bot still runs if DB is down (logs only). |
| FastAPI dashboard | Yes | `/metrics`, `/replay`, `/strategy-analysis`, `/health`, `/set_mode`. |

## Known logic and design limitations

These are inherited from or adjacent to the original design; they are **not** a production-ready trading system.

1. **No real broker execution** — `execute_trade` simulates PnL with `random.uniform`. Switching to **live** does **not** place OANDA orders. `OANDA_ACCOUNT_ID` is currently **unused**.
2. **Strategy names are labels** — `scalp` / `trend` / `mean_reversion` do not change signal logic; only the meta-learner weights and random selection differ.
3. **Session clock** — `in_active_session` and `pre_close_adjustment` compare **UTC** wall time to the configured `HH:MM` strings. If you meant London or New York session, convert those windows to UTC or use a timezone-aware helper.
4. **Daily report timezone** — `daily_report` uses **local** `datetime.now().date()` while sessions use **UTC**, so “one report per calendar day” may not align with FX session boundaries.
5. **`evolve()` can silence the bot** — After enough trades, strategies with Sharpe &lt; 0 are disabled. If **all** are disabled, `select_strategy()` returns `None` and **no trades** run until restart or code changes.
6. **`exit_price` in logs** — `price + pnl` is a placeholder, not a realistic exit quote for FX.
7. **Single process** — The trading loop starts inside FastAPI’s lifespan. Run **one** container / **one** uvicorn worker; multiple replicas would start **multiple** bots and corrupt assumptions about equity and positions.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose v2
- OANDA API token with access to the instruments you trade

## Quick start (Compose)

1. Copy environment template:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and set at least `OANDA_ACCESS_TOKEN`.

3. Build and start:

   ```bash
   docker compose up --build -d
   ```

4. Check health (Compose maps **host 8001 → container 8000** by default):

   ```bash
   curl http://localhost:8001/health
   ```

5. Dashboard and API (default host port **8001**):

   - `GET http://localhost:8001/metrics`
   - `GET http://localhost:8001/replay`
   - `POST http://localhost:8001/set_mode?mode=practice` or JSON body `{"mode":"live"}`

6. Logs:

   ```bash
   docker compose logs -f bot
   ```

7. Stop:

   ```bash
   docker compose down
   ```

   Add `-v` to remove the Postgres volume (`pgdata`) and wipe stored trades.

### Use host port 8000 instead

If nothing else is bound to 8000, set in `.env`:

```env
BOT_PORT=8000
```

Then `docker compose up -d` again.

### Optional: Ollama in Docker (local LLM)

The repo includes an **`ollama` service** that is **off by default** (Compose **profile** `ollama`).

1. In **`.env`**, aim the bot at the in-network Ollama API and disable the local quant stub if you want:

   ```env
   OPENAI_BASE_URL=http://ollama:11434/v1
   OPENAI_MODEL=llama3.2
   OPENAI_API_KEY=ollama
   OPENAI_JSON_MODE=false
   AI_DISABLE_STUB=true
   ```

2. Start **db**, **bot**, and **ollama**:

   ```bash
   docker compose --profile ollama up -d --build
   ```

3. **Pull a model** inside the Ollama container (once per model):

   ```bash
   docker compose exec ollama ollama pull llama3.2
   ```

4. Ollama is also published on the host at **`OLLAMA_HOST_PORT`** (default **11434**) so you can use `ollama` from the host or open its API at `http://localhost:11434`.

The **bot** does not `depends_on` **ollama** (so the default stack works without the profile). If the bot starts before Ollama is healthy, the first LLM calls may fail until Ollama is ready; later cycles will succeed.

**GPU:** On Linux with NVIDIA, you can add a `deploy.resources.reservations.devices` block to the `ollama` service per [Ollama Docker docs](https://github.com/ollama/ollama/blob/main/docs/docker.md). On Windows, GPU setup depends on Docker Desktop / WSL2; CPU mode still works, slower.

## Image-only (no Compose)

```bash
docker build -t forex-bot .
docker run --rm -p 8000:8000 \
  -e OANDA_ACCESS_TOKEN="your_token" \
  -e TRADING_MODE=practice \
  forex-bot
```

Without Postgres, trade rows are not persisted; the API still serves in-memory metrics.

## Production checklist (if you ever go beyond a demo)

- Secrets: inject via orchestrator secrets, not committed `.env`.
- Do not scale the `bot` service horizontally without redesigning state and the trading loop.
- Add real order placement behind a feature flag, idempotency, and risk checks if you intend **live** execution.
- Use HTTPS in front of the API (reverse proxy) and protect `POST /set_mode`.
