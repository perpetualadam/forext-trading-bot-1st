# Weekend restart assessment

The weekend does not change the technical blockers. Market closure is not deployment approval. This stage did not ask the broker whether positions or orders exist, and it does not claim that they do not. It does not claim that every instrument is closed. A long recovery can still be in progress when the market opens.

`WOULD_RESTART_APPLY_NEW_CODE`: NO.

Compose bind-mounts only `./data/ops` and `./data/research/v2_shadow`. It does not mount `forex_bot` or `main.py`. The historical container was created from an image on 2026-10-08. Working-tree Python that differs from that image stays on disk. Restarting the container starts the image again. The G.12 sample already shows `bot_loop.py`, `oanda_client.py`, `oanda_exec.py`, `live_manage.py`, and `decision_skip_log.py` differ, and `market_provenance.py` was absent. Current container mounts were not re-inspected, so this conclusion uses the compose file plus the image identity record, not a fresh inspect.

`IS_A_REBUILD_REQUIRED`: YES, before the current source can run in a container. A rebuild is not authorised. Staging is not a rebuild.

`IS_THE_CURRENT_SOURCE_DEPLOYABLE`: NO. Dependencies are unpinned, no candidate image exists, startup writes safety state and calls OANDA, the safety schema can be destroyed, and there is no verified rollback.

`IS_STARTUP_SAFE`: NO for the current source. `RESTART_SAFETY_UNVERIFIED` for the historical image. The sampled `app.py` and `live_safety.py` already perform the safety rewrite and the AccountSummary call. A weekend restart of the existing container would run those paths if that image is still the one in use.

`IS_ROLLBACK_VERIFIED`: NO. The historical image is only `ROLLBACK_CANDIDATE_PARTIALLY_VERIFIED`. There is no verified rollback target. The image `sha256:a19a2208fcf30f8fa1cf61442cf021dec6d99d809b6907836c834922bfe3e2a5` must not be used.

`IS_WEEKEND_DEPLOYMENT_APPROVED`: NO.

Open positions, pending orders, and broker-side state remain UNKNOWN. Startup database writes and the safety rewrite do not become safe because the session is quiet. Reopening would meet whatever orders the restarted process is able to manage, using image code that is not the current tree.
