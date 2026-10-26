# Runtime entrypoint

Dockerfile line 81 declares the command `uvicorn forex_bot.app:app --host 0.0.0.0 --port 8000`. There is no `ENTRYPOINT`. The effective entrypoint of the base image is unverified. The module is `forex_bot.app:app`. The working directory is `/app`. The runtime user is undeclared.

Compose does not override the command, entrypoint, user, or working directory. It names environment variables and two bind mounts. `PYTHONUNBUFFERED` is set in the Dockerfile. A log destination beyond the process standard streams is not declared. The bot service has no health check and no restart policy. The database service does not supply those bot settings.

None of this was executed. Local Compose text is not a production runtime observation.
