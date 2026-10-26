# Deployment state comparison

Five states stay separate.

## State A — historical production image

Identity last recorded in G.14.2, not refreshed: container `forexttradingbot1st-bot-1`, id `5fcbcff7173eee98f6228b901fab96fd24474038852ef1f4cc3fbccd138edd32`, image `sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25`, tag `forexttradingbot1st-bot:latest`. Created 2026-10-08. Current identity: `HISTORICAL_ONLY_NOT_REVERIFIED`.

G.12 history showed `COPY forex_bot ./forex_bot` and `COPY main.py .`. The entrypoint was uvicorn on port 8000. Restart policy was `no`. File bytes were sampled for 10 of 229 application files. The save archive was deleted and was not opened.

## State B — current working tree

Git HEAD `d080d897945bc44fa37c02caab504ed707146bec` at 2026-10-10 10:56 +0100, which is after the image timestamp. Allowlisted Python matches that HEAD. The only allowlist byte change versus G.10 is the Dockerfile. Staging matches this tree.

## State C — G.14.1 staged context

`C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2`. Re-hashed in D.1: 63 files, 617279 bytes, manifest `8597768f9b351ee5a8b8c3750cb4df12880a25414dfb4e6aab072e1fe2b3b33b`. Not modified. Not an image.

## State D — future candidate image

Does not exist. G.14.2 recorded no candidate tag.

## State E — future deployed container

Does not exist as a verified deployment. The running container, if it still exists, is State A until someone inspects it again.

## What can be proven

| Item | A versus B |
| --- | --- |
| `app.py`, `live_safety.py`, `database.py`, `main.py` | Same hash in the G.12 sample and the working tree |
| `bot_loop.py`, `oanda_client.py`, `oanda_exec.py`, `live_manage.py`, `decision_skip_log.py` | Different hash in the sample |
| `market_provenance.py` | In the working tree and staging. Absent from the sample. |
| Other allowlisted modules | UNKNOWN in the image |
| Packaging | Image used a broad package COPY. Working tree uses an explicit list. |
| Dependencies | Image site-packages were not re-read. Working tree requirements are unpinned. |
| Startup | Shared `app.py` calls safety rewrite, DDL, AccountSummary, reconciliation, and `run_bot`. The body of `run_bot` and the broker modules differ. |
| Safety file | Behavior is in the shared `live_safety.py`. Live file contents UNKNOWN. |
| Database | DDL source matches. Live schema UNKNOWN. |
| Shadow mount | Compose mounts `./data/research/v2_shadow`. Contents UNKNOWN. Image writer may not match current `bot_loop.py`. |
| Config | Compose has no working-tree diff. Live environment UNKNOWN. `.env` was not read. |
| Entrypoint | Same command string in the Dockerfile and the G.12 record. |
| Permissions | Not compared. Staging directory mode was recorded earlier as `drwxrwxrwx` and is not a production runtime. |
| Recovery | No verified procedure. Image `sha256:a19a2208fcf30f8fa1cf61442cf021dec6d99d809b6907836c834922bfe3e2a5` is unsafe and is not a target. |

Files excluded from the repaired package include tests, research, `forex_bot/shadow`, `forex_bot/decision_quality`, the two sensitive backups, and the repository root. The historical broad COPY may have included package subtrees that the repaired Dockerfile omits. That inclusion was not re-listed from image layers.

An image tag does not prove current contents. Docker was not used to fill the gap.
