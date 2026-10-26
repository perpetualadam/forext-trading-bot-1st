# Historical deployment context

These values are historical observations. Docker was not queried. None of them is a current production fact.

- Container name: `forexttradingbot1st-bot-1`
- Container ID: `5fcbcff7173eee98f6228b901fab96fd24474038852ef1f4cc3fbccd138edd32`
- Running image: `sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25`
- Unsafe old image, not a rollback option: `sha256:a19a2208fcf30f8fa1cf61442cf021dec6d99d809b6907836c834922bfe3e2a5`
- Historical restart policy: `no`
- Historical base-image tag: `python:3.12-slim-bookworm`
- Historical local base-image ID: `sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254`
- Historical registry digest: unverified

A tag, a local image ID, and a registry digest are different identities. A mutable tag does not identify bytes. The historical running image is not a verified rollback target, and it is not known to contain the D.2–D.14 working-tree safety fixes. Availability of either image was not checked.

D.1 recorded deployment and rollback as NO-GO. D.15 recorded lifecycle tests as an offline pass and left the same deployment blockers open. Those reports do not prove the current production container.
