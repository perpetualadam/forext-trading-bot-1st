# Compose target declaration

Evidence level: `CURRENT_LOCAL_FILE_VERIFIED`. Compose was parsed as text and was not executed. Real environment files were not read. Default secret values are not recorded here.

The bot service:

- `platform`: absent. Absence is not `linux/amd64`.
- `build`: line 17, context `.`. No `build.platforms`, no Dockerfile path, and no target stage.
- `image`: absent on the bot service.
- Command and entrypoint: absent. The Dockerfile command would apply only if that image were built. This file does not prove a built image.
- User and `working_dir`: absent.
- Environment: lines 22–198 name variables only.
- Mounts: lines 201–203, `./data/ops:/app/data/ops` and `./data/research/v2_shadow:/app/data/research/v2_shadow`.
- Health check: absent on the bot. The db service has one at lines 10–14. The optional ollama service has one at lines 221–226.
- Restart: absent on the bot. Ollama line 227 says `unless-stopped`. That policy is not the bot policy.
- Resource constraints: absent.
- Architecture: absent.

Other images in the same file are not the bot runtime. Line 3 is `postgres:16-alpine`. Line 214 is `ollama/ollama:latest` under the `ollama` profile.

`deploy/docker/collect-due.example.sh` line 13 names `python:3.13-slim` and says it must not be merged into the live trading-bot container. It does not select the bot platform.
