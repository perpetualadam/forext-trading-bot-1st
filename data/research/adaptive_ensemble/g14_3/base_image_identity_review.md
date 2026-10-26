# G.14.3 base-image identity review

These identities are different. G.14.2 recorded only the first two, and the second repeated the first.

| Identity | Evidence |
| --- | --- |
| Local image ID | `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254` |
| Repository tag | `python:3.12-slim-bookworm`, mutable |
| RepoDigests field | `python@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254` |
| Registry manifest digest | `UNKNOWN` |
| Multi-platform manifest-list digest | `UNKNOWN` |
| Platform-specific image manifest | `UNKNOWN` |
| Image configuration digest | not separately recorded |

The RepoDigests value has no registry hostname and is the same hex as the image ID. It is not accepted as a registry digest. No digest was invented. No pull and no retag were performed. Presence of the local tag was not rechecked in this stage.

Classification remains `BASE_IMAGE_DIGEST_UNVERIFIED`.

## Future reference options

- An independently verified registry digest, including the registry hostname and a digest that is not merely the image ID, could become `FROM`. That evidence does not exist.
- A controlled local reference can check, immediately before a later build, that `python:3.12-slim-bookworm` still has the recorded image ID. That check needs a new Docker-inspect approval and still does not create a registry pin.
- A validated immutable base artifact would be an exported image with a recorded size and SHA-256, stored outside OneDrive. That archive does not exist. Do not recreate the deleted G.12 archive.

## What would prove the base of a future build

Record the built image's parent or base layer and show it equals the intended image ID or a later-verified manifest digest. Image history alone is not that proof. `--pull=false` was not re-run.

## `--pull=false`

`--pull=false` avoids a refresh when the tag is already local. It does not keep Docker from pulling a missing tag. It does not stop `pip install` from using the network. It does not freeze the tag if someone retags the name before the build. It is not network isolation.
