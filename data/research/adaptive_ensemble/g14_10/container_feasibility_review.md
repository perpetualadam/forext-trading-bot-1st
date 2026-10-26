# Disposable container feasibility

Classification: `CONTAINER_FEASIBILITY_PLAUSIBLE_UNVERIFIED`

Verified isolation: no. Historical Docker metadata is not a current isolation proof and was not refreshed.

## Historical evidence only

From `data/research/adaptive_ensemble/g14_2/docker_daemon_metadata.json`, level 4:

- Server version `29.1.3`.
- API version `1.52`.
- Platform name `Docker Desktop 4.57.0 (215387)`.
- Kernel `6.6.87.2-microsoft-standard-WSL2`.
- Engine OS `linux`, architecture `amd64`.
- The daemon was reachable then. Configuration was not modified.
- Commands used then were `docker version` and `docker info`. Those commands were not run in G.14.10.

From `running_container_identity.json`, level 4:

- Container `forexttradingbot1st-bot-1`.
- ID `5fcbcff7173eee98f6228b901fab96fd24474038852ef1f4cc3fbccd138edd32`.
- Image `sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25`.
- Status running, restart count 0, identities matched.
- Environment values were not collected.
- Rollback status `ROLLBACK_CANDIDATE_PARTIALLY_VERIFIED`.

From `base_image_preflight.json`, level 4:

- Tag `python:3.12-slim-bookworm` was present locally.
- Image id `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`.
- The repo-digest field repeated that image id and did not name a registry.
- Classification `BASE_IMAGE_DIGEST_UNVERIFIED`.
- The known running container used a different image id.

`DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED` remains. This stage did not inspect the socket, volumes, or the running container.

## Claims that historical evidence does not support

- Namespace isolation of a future acquisition container.
- Current privilege settings, read-only root, or a dedicated writable volume.
- That a bind mount would be absent. A bind mount of a host path would repeat the G.14.8 open.
- Docker socket exposure. The socket was not opened here. Historical reachability shows that, at G.14.2, a client on this host could talk to the daemon. It does not measure the current pipe ACL.
- Rootless mode. Not recorded.
- Default network, or a network-denied mode. Not measured now.
- Credential injection and environment inheritance. G.14.2 did not collect environment values. This stage did not either.
- Same-user control of the daemon today. Historical commands ran. That is not a current ACL reading.
- Container escape. Not tested. Not assumed.
- Separation from the production container. The historical record is one daemon and one running production container. A second container on that daemon is not assumed harmless.

## Export and import

No acquisition volume exists. Export from a container onto a user-writable Windows path is a host `CreateFileW`. That path is subject to the demonstrated substitution. Image provenance does not fix that open.

## Target compatibility

The historical engine architecture was `linux/amd64`, which matches the intended architecture label only. It does not supply Python patch, SOABI, glibc, pip, wheel tags, or a registry digest. Those remain unknown.

## Classification

`CONTAINER_FEASIBILITY_PLAUSIBLE_UNVERIFIED`

Docker was observed in the past on this machine, so the category is not `UNKNOWN` and not `BLOCKED` by absence. It is not supported as an isolation boundary. The production container's historical presence on that daemon is a reason not to select a container. It is not a fresh inspection. No container is selected.
