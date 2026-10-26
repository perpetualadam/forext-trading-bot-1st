# Startup and restart risk audit

Classification: `RESTART_SAFETY_UNVERIFIED`.

The lifespan was read and not executed. `forex_bot/app.py` in the working tree has the same SHA-256 as the G.12 image sample (`77888f0fa40b5a2935913be6d9b8770c1df0aa204d21c72537cef9e01ac0f70d`). A restart of that image would run this lifespan only if the container still uses that image. D.1 did not check the live container. Calls made from the lifespan into `bot_loop.py`, `oanda_client.py`, and `oanda_exec.py` may differ, because those files differed in the image sample.

Historical blocked state is not proof that the next startup leaves the file unchanged.

| Operation | Trigger | Where | Unconditional | Guard | Persistent write | OANDA | Database | Can activate trading | Depends on existing data | Tested here | Verified in image |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Logging setup | Lifespan enter | `app.py` 253 | Yes | No | No | No | No | No | No | No | Same app.py hash only |
| Fail-closed safety load and rewrite | Lifespan enter | `app.py` 254; `live_safety.py` 259-298 | Yes | Invalid document becomes a blank BLOCKED file | Yes, JSON replace | No | No | Restores strategy `active` from the file. Does not force them inactive when the file is valid. | Yes, `data/ops` | No | live_safety.py hash matched the sample |
| PostgreSQL connect and DDL | Lifespan enter | `app.py` 256; `database.py` 115-140 | Yes | Failure logs and returns None | Yes, commit of CREATE/ALTER | No | Yes | No | Yes, existing tables | No | database.py hash matched |
| Load open orders | After connection | `app.py` 260 | Yes | Function body not fully read | Possible | Unknown | Yes if connected | No | Yes | No | Unknown |
| Load reconcile state | After connection | `app.py` 261 | Yes | Not fully read | Possible | Unknown | Yes | No | Yes | No | Unknown |
| Build broker client | Lifespan | `app.py` 262; `oanda_client.py` 104 | Yes | Returns None if config missing | No | No by itself | No | No | Credentials | No | oanda_client.py differed |
| AccountSummary | Lifespan | `app.py` 264; `oanda_client.py` 140-158 | Attempted | Exception is logged | Cached summary | GET `/v3/accounts/{id}/summary` | No | No | Account id | No | Caller matches; callee differed |
| Reconciliation once | Lifespan | `app.py` 269; `reconciliation.py` 849 and 724 | Attempted | Exception logged | Local positions and reconcile metadata | Position and pending-order reads. Comment says it does not send orders. | Yes via `_save_reconcile_state_to_db` | Can change local position records | Broker and local positions | No | oanda_exec.py differed |
| Entry-block log | If not paper | `app.py` 275-280 | Only when mode is not PAPER | Logs only | No | No | No | No | Mode and safety | No | app.py matched |
| Mark started and alert | Lifespan | `app.py` 283-288 | Yes | No | Operational message | Possible via alert path | Event log is loaded just before | No | No | No | app.py matched |
| Background tasks | Lifespan | `app.py` 291-297 | Yes | No | Ongoing | Reconciliation loop and `run_bot` | Ongoing | `run_bot` cycles symbols | Yes | No | `run_bot` lives in differing bot_loop.py |
| `run_bot` cycle | Task | `bot_loop.py` 1743-1768 | Loop | Exceptions logged, then sleep | Portfolio and shadow files | Account summary and pricing each cycle | Possible | Strategy cycle runs | Market and safety | No | File differed |
| Shutdown | Lifespan exit | `app.py` 300-328 | On exit | Cancels tasks | Stop alert | Possible alert | No flatten in this block | Stops the loop | No | No | app.py matched |

`initialise_fail_closed` always sets effective live-order authorisation to BLOCKED. If the durable document is valid and says a strategy is active, that flag is applied. If the document is missing, unreadable, or has a different `schema_version`, it is replaced with a blank document whose six strategies are inactive, and that replacement is written.

Compose does not bind-mount the source tree. It bind-mounts `./data/ops` and `./data/research/v2_shadow`. A container restart therefore does not load working-tree Python. It does re-run whatever lifespan is already inside the image, including the safety rewrite and the AccountSummary call that are in the sampled `app.py`.

Restart policy recorded by G.12 for the bot container was `no`. Compose does not set a restart policy on the bot service. The ollama service, which is behind a profile, uses `unless-stopped`. None of this was re-inspected on the live container.
