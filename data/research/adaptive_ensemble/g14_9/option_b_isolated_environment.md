# Option B — isolated acquisition environment

Classification: `TRUST_ANCHOR_DESIGNED_NOT_IMPLEMENTED`

Environment selection: `ENVIRONMENT_SELECTION_REQUIRES_FURTHER_EVIDENCE`

No environment was created. No container, virtual machine, WSL distribution, sandbox, or restricted process was started. Docker was not invoked.

## What isolation would have to mean

The acquisition writes must land on a filesystem object the demonstrated same-user attacker cannot swap before the open that captures the handle. The later host read of any exported bytes has the same requirement. A guest that verifies its own files does not bind a later host `CreateFileW` on a user-writable export path. That second open is the G.14.8 race again.

Isolation that stops at the guest, and then copies onto a normal Windows directory, relocates the vulnerable open to the import.

## Candidate types

### Restricted Windows process

A restricted token of the same user is not a different principal. G.14.8 already replaced a directory owned by this user without elevation. The prompt's own constraint applies: a restricted process is not assumed to be a boundary against that user. This subtype is ineligible on current evidence. No restricted token was created or tested.

### Disposable WSL distribution

This stage did not list or start WSL distributions. There is no local evidence of a distro with automount disabled. A host path mounted into the guest would be opened through the host's path lookup. The existing destination check rejects a path containing `wsl$` (`tests/g14_4_acquire.py`). That is a denylist, not a measurement of WSL isolation. A same-user host process reaching a guest filesystem through a host path would stand outside any guest-only policy. WSL is not selected.

### Disposable virtual machine

A guest disk is not a Win32 directory handle until some host component opens it. That is the conceptual difference from Option A. It is not evidence. This stage did not inventory a hypervisor, did not read virtual-disk ACLs, and did not show that this user cannot replace a disk path before the hypervisor opens it. Many desktop hypervisors are usable by the same interactive user that G.14.8 already treated as the attacker. If that user can replace the disk file, the boundary has the same shape as the directory swap, one layer lower. A VM is not selected.

### Disposable container

A container is not a virtual machine. Historical Docker observations from G.14.2 were not refreshed. `DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED` remains. The running production container was not inspected and must not be used as an acquisition environment.

A bind mount of a host path repeats `CreateFileW` on that path. A named volume still has to be created and later exported by a daemon. Whether another process of this user can talk to that daemon was not measured. Measuring it would be a Docker command, which this stage does not run and which a later stage would have to approve separately. Because the production container has historically been on that daemon, a candidate container is not assumed to be isolated from it. A container is not selected.

## Trust anchor the design would need

The anchor would be the isolation boundary's own root filesystem, created by a principal this user cannot impersonate, with no host path mounted into it, and with export performed by that same boundary after the producer has stopped. Current evidence does not establish that anchor. The classification is therefore designed, not implemented, and not verified.

## Filesystem, credentials, and production

A future environment, if one is ever approved, would have to start with no repository mount, no OneDrive mount, no Docker socket, no production mounts, no operational-state mounts, no shadow-state mounts, no live database address, and no broker credentials. Absence of those mounts would be a configuration to prove later. It was not proved here.

The trading bot and this acquisition workflow would stay separate only if the environment cannot reach the bot's token, database, or OANDA credentials. Same-user host processes can read this user's profile unless the environment does not run as this user and does not mount the profile. That separation is unevidenced.

## Network

The environment would still need an explicit network policy before any metadata or wheel request. Isolation does not approve `pypi.org` or `files.pythonhosted.org`. A first validation phase would have no network at all. That phase was not started.

## Target compatibility

The production target is Linux, x86_64, CPython 3.12, image tag `python:3.12-slim-bookworm`. A Windows process cannot observe that image's patch level, SOABI, glibc, or pip by itself. A Linux guest might eventually be a place to observe them. The historical local image id `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254` is not a registry digest. No guest was started, so those values stay unknown. `TARGET_RUNTIME_COMPATIBILITY_PROFILE_INCOMPLETE` remains.

## Phases, none of which ran

1. Environment creation. Not done. Would need its own approval.
2. Offline validation of the environment. Not done.
3. Offline synthetic acquisition inside it. Not done.
4. Package-source metadata access. Not approved.
5. Real wheel downloads. Not approved.
6. Artifact verification. The existing handle-byte verifier could be reused only after a real anchor exists.
7. Controlled export. Not designed as an implementation. The import open is a second race unless the export medium is outside this user's write set.
8. Independent host verification. Must recompute hashes. Must not trust a guest manifest alone.
9. Candidate packaging. Separate from production packaging. Not approved.
10. Candidate build. Docker build is not approved.

## Privileges and operational cost

A boundary this user cannot reconfigure is likely to need a principal or hypervisor right this account does not already have. That is an inference from the G.14.8 same-user result, not a measurement of a particular product. Asking for administrator rights is not part of this stage.

Docker Desktop interaction is an open risk for the container subtype because the production container's daemon behavior is unverified. A VM or WSL instance can also be backed by the same Desktop installation. That overlap was not inspected.

Rollback of the trading bot is unrelated to an acquisition guest only while the guest cannot change the running container, the image, or the live database. Keeping that true is a future control, not a present one. `NO_VERIFIED_ROLLBACK_TARGET` stays.

## Deterministic testing

Synthetic acquisition tests could be repeated inside a future guest. They would still not prove the host import. A test plan would need a same-user process outside the guest attempting to replace both the guest disk and the export path. That test was not run, because running it would create the environment this stage forbids.

## Required evidence before any subtype could be chosen

- The principal that owns the boundary.
- Whether this user can modify that principal's objects, measured without creating a new environment if an existing one is only inspected, or under a separate creation approval if not.
- Whether host paths are mounted in.
- Whether the production container, its mounts, and the Docker socket are reachable.
- Whether export bytes can be hashed without a host path open this user can race.
- Network default of deny, observed rather than configured in a document.

Until those exist, no subtype is justified. `ENVIRONMENT_SELECTION_REQUIRES_FURTHER_EVIDENCE`.

## Major risks

- Treating a container, WSL distro, or restricted token as a boundary without evidence.
- Bind-mounting the repository, OneDrive, or an export directory and recreating the race.
- Sharing a daemon with the running trading container.
- Letting the guest reach OANDA, the live database, or credentials.
- Trusting a guest manifest on the host.
- Using a Linux guest as if it had already identified the production image's glibc and wheel tags.
