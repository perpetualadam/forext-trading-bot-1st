# D.29 SAFETY AND BUDGET FINALISATION

This document finalises the figures. It does not authorise the transfer.

The eight compressed layer descriptors declare 94,726,961 bytes: 47,558,478 for linux/amd64 and 47,168,483 for linux/arm64/v8. Each storage response is capped at the declared size of its own digest. The largest declared object is 28,249,323 bytes.

The request ceiling is 18 serial GET requests and zero retries: one anonymous registry request, one token request, eight authenticated registry requests, and eight storage requests. Non-layer bodies stay under the earlier 1,048,576 byte cap. The total body-read ceiling is 105,212,721 bytes. Disk retention after a match is only the 94,726,961 declared layer bytes.

No transfer rate was measured. The per-request ceiling is 120 seconds, taken from the Dockerfile pip timeout declaration. Eighteen serial requests make a 2,160 second stage ceiling. The old 30 second config-blob timeout is not reused for these layers.

registry-1.docker.io and auth.docker.io are the proposed registry and token hosts. production.cloudfront.docker.com is a historical observation, not an approval. A 307 therefore stops a future stage unless a new approval names the storage host. The registry token is not sent to storage, and signed URLs are not stored.

A matching download still would not be extracted, decompressed, or executed. It would not measure Python ABI or libc, and it would not describe the final bot image or the VPS.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
