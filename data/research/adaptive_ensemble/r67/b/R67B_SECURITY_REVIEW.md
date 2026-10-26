# R.67B Security review

Design-only stage. Markdown under `data/research/adaptive_ensemble/r67/b/` is the only write. Operational Python, R.56–R.67A reports, configuration, and git history were not modified.

## R.67A gate

R.67A was read in full before any R.67B state was drawn. The five documents agree on observation versus management versus execution authority, on the import default, on protection evidence, and on restart. No incomplete section and no contradiction blocked this stage. `CLOSE_AMBIGUOUS` stays an ownership label. The close lifecycle uses its own state names and cites that label when a pre-send commit has happened.

The user named R.67A as the approved contract for R.67B. The check in this thread is a consistency review of those files against the source hashes below.

## Isolation

| Check | Result |
| --- | --- |
| Operational Python edited | No |
| `main.py`, `forex_bot.app`, `run_bot` executed | No |
| `forex_bot` imported | No. `forex_bot.config` calls `load_dotenv()`, and `database.py` imports that config. The schema was read as text. |
| `.env`, secrets, credentials, account payloads | Not opened |
| OANDA, including the practice host | Not contacted. `REAL_NETWORK_EXECUTION_NOT_TESTED` |
| Orders placed, amended, or closed | No |
| Source gate or activation permit | Unchanged. No permit was created. |
| R.62–R.65 integrated | No |
| Working tree cleaned, reset, or overwritten | No |
| Strategy, sizing, stop distances, trading parameters | Unchanged. `BROKER_SNAPSHOT_FRESHNESS` and `PROTECTION_FRESHNESS` stay unnamed. |
| Automatic stop attachment or stop amendment | Not designed as an action. Not sent. |
| Database migration or table rewrite | Not executed. Additive records are specified only. Existing tables stay. |

The installed `oandapyV20` package was read as files for `PositionClose`, `PositionCloseRequest`, `ClientExtensions`, `Units`, and the position-close response sample. It was not imported in this stage and no `client.request` ran.

## Source boundary

Commit `d080d897945bc44fa37c02caab504ed707146bec`. Rechecked before the design. `CHANGED []` against `R67A_SECURITY_REVIEW.md`.

| Path | SHA-256 |
| --- | --- |
| `forex_bot/bot_loop.py` | `6e953f7a2b0aa93f1f65c7b411d117e74cba6adf523f8514847bc69a7ea5c796` |
| `forex_bot/live_manage.py` | `60d87b8665620743467832758032857e975d32da15322307a0c331009cc7b25d` |
| `forex_bot/reconciliation.py` | `295686792ab017cfc8dfba8fd0add6b2b66a3008304ade141e899af7e86e776b` |
| `forex_bot/oanda_exec.py` | `f4beb250d81852d8ee4f22af06ab33194c6b4ba1bf6f9b1a6b5d11d3b7b265c8` |
| `forex_bot/positions.py` | `e63ac07e6677ae5707a2a75888bcd5c39df5957ab34547659546e8546d537f2a` |
| `forex_bot/execution.py` | `6602e363171e3aac4bc4b597ddb805c454c7ca40f7d1fe3fddf542f6a1ab86e2` |
| `forex_bot/trading.py` | `5ac3981690fe9536edaedfd35a933d17fc37a1e4a77c5c3e9b47517db6300fc7` |
| `forex_bot/app.py` | `1883d3c94a570b66782b7079bcd64d7657c83c0cd6faa385cab7a65bc2d56bd1` |
| `main.py` | `4711818ad85b12d1be94e13a08182ff60881416302a84a573fe18f37a043d3eb` |

Additional files read for persistence and exit evidence, not edited:

| Path | SHA-256 |
| --- | --- |
| `forex_bot/broker_exit.py` | `d9920eed6160c5f26e1db7ee34095488b3457755e5dbf21cffbeda08eb798c12` |
| `forex_bot/database.py` | `be83fc2a485af0f392203562a8286082587b0824f235557b6036e69f661f840d` |

The production entry refusal stays in force (`bot_loop.py` 3323–3328, 1125–1134, `R66-01`). Observation of a broker position is not permission to open or to close.

## Authority this design refuses

- `log_only`, `auto_fix`, `execution_kind`, a trade id, and a RAM row do not enter `MANAGEMENT_AUTHORISED` and do not authorise `PositionClose` (`R66-04`, `R67A` invariants 3, 4, and 9).
- A failed, timed out, or incomplete snapshot is not proof the broker is flat.
- A timeout is not a rejection and not a successful close, and it does not permit a repeat (`R66-11`).
- An HTTP body without fill units and `tradesClosed` is not a full close (`R66-10`).
- A partial fill does not delete the remaining exposure.
- A local fallback price is not `BROKER_PROTECTED` (`R66-05`). No stop is sent to repair `UNPROTECTED_CONFIRMED` or `PROTECTION_UNKNOWN`.
- Restart does not restore a `CLOSE` grant. `CLOSE_SUBMITTING` reloads as `CLOSE_OUTCOME_UNKNOWN`.
- Client extensions are not treated as server-side idempotency. The installed request model has no idempotency key. Echo on a fill is `NOT_VERIFIED`.
- The bot does not disable the account or block a human using the broker's own controls. An unresolved close still must not send a competing close.
- No global lock is held across a broker wait. The linearisation point is the durable commit.

## Unresolved broker semantics

| Topic | Classification |
| --- | --- |
| Live OpenPositions, TradeDetails, and PositionClose bodies | `NOT_VERIFIED` |
| Server-side idempotency of `PositionClose` | Not present in the installed client. Not assumed. |
| Echo of `longClientExtensions` or `shortClientExtensions` | `NOT_VERIFIED` |
| Host acceptance of decimal unit strings, and of the sample token `ALL` | `NOT_VERIFIED`. This design forbids `ALL`. |
| Partial-close allocation across trades when `tradesClosed` is absent | `NOT_VERIFIED`. The operation stays in reconciliation. |
| Account hedging permission | `NOT_VERIFIED`. Both sides open still forbid management. |
| `TradeClose` behaviour | Unused by the bot. Not selected by this design. |
| Account currency and runtime execution mode | `NOT_VERIFIED`. `.env` was not read. |

`PositionClose` in the installed sample can list `tradesClosed` with per-trade units. The operational parser keeps price and P&L only. Requiring those sample fields as evidence is a design rule. It is not a claim that a live host always sends them.

## Production status

The working tree can still import under `log_only` when broker mode is on, still share one RAM book, and still repeat a close after a timeout. R.67B records the machines that would refuse those outcomes. It does not install them.

Production trading remains NO-GO.
