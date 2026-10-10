# Stage G.11 readiness

Classification: `READ_ONLY_AUDIT_COMPLETE_ROLLBACK_UNVERIFIED`

The running container is `forexttradingbot1st-bot-1`, id `5fcbcff7173eee98f6228b901fab96fd24474038852ef1f4cc3fbccd138edd32`. Its image id is `sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25`, created `2026-10-08T22:24:01Z`. That id matches the historical Stage A image. It does not prove the image contains the later safety repairs, and no second rollback image is present.

The unsafe image `sha256:a19a2208fcf30f8fa1cf61442cf021dec6d99d809b6907836c834922bfe3e2a5` is not local and is rejected.

No deployment is authorised. Docker context semantics and the live database remain unverified.
