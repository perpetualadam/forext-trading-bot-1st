# Historical base image

D.16 and G.14.5 record the tag `python:3.12-slim-bookworm` and the local image ID `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`. G.14.2 recorded the same hex as a repository digest field with no registry hostname, and recorded that local image as `linux/amd64`. G.14.5 classified the registry manifest digest as unknown.

What this establishes: a past local daemon had an image with that ID under that tag, and a past report described that image as `linux/amd64`.

What this does not establish: a registry digest, current registry availability, the bytes behind today's tag, the intended future server architecture, or a pin that can be written into `FROM`. Docker was not queried. The tag remains mutable. The historical running image `sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25` is a different ID and is not a verified rollback target.
