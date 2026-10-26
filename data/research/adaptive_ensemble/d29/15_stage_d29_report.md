# STAGE D.29 — OFFLINE OCI LAYER ACQUISITION SAFETY AND BUDGET FINALISATION

## 1. EXECUTIVE SUMMARY

- Overall classification: `D29_OFFLINE_ACQUISITION_BUDGET_FINALISED`
- Production source modified: no
- Network requests: 0
- Image layers downloaded: none
- Execution of this budget: NOT AUTHORISED

## 2. LIVE SAFETY

- Production container changed: no
- Broker requests: none
- Broker mutations: none
- Production database access: none
- Telegram network requests: none
- Docker, WSL, and VM commands: none
- Image-layer downloads: none
- Image-layer extraction: none
- Live-order authorisation: historically BLOCKED. Current production authorisation was not independently verified.
- Strategy activation: none. The six strategies remain historically inactive.

## 3. BASELINE

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working tree: dirty before D.29. HEAD does not identify the working-tree bytes.
- Protected hashes: the ten expected digests match.
- D.28 layer inventories and the five OCI objects were rehashed and matched.

## 4. FINALIZED BODY BUDGET

- AMD64 declared compressed bytes: 47,558,478
- ARM64 declared compressed bytes: 47,168,483
- Combined layer bodies: 94,726,961
- Per-layer cap: the declared size of that digest
- Largest layer: 28,249,323 bytes
- Non-layer body cap: 1,048,576 bytes, reused from the D.24-R2 config retrieval
- Non-layer responses inside the ceiling: 10
- Total body-read ceiling: 105,212,721 bytes
- Disk after a verified match: 94,726,961 bytes
- Decompressed bytes: not in this budget

## 5. FINALIZED REQUEST AND TIME BUDGET

- Method: GET
- Retries: 0
- Serial requests: yes
- Request ceiling: 18
- Sequence: one anonymous registry GET, one token GET, eight authenticated registry GETs, eight storage GETs
- Socket timeout: 120 seconds, from the Dockerfile pip timeout declaration
- Stage ceiling: 2,160 seconds
- Measured registry transfer rate: MISSING
- The historical 30 second config timeout is not applied to these layer bodies.

## 6. HOST AND REDIRECT RULE

- Proposed registry host: `registry-1.docker.io`
- Proposed token host: `auth.docker.io`
- Storage host: NOT AUTHORISED
- Historical storage host, not approved: `production.cloudfront.docker.com`
- Redirects followed under the current approval: 0
- A future 307 stops the stage unless a new approval names the storage host.
- The registry token is not sent to storage.
- Signed URLs are not stored.
- Approval status: NOT AUTHORISED.

## 7. INTEGRITY RULES

- Hash each body while reading it.
- Keep a layer only when its size and SHA-256 match the manifest descriptor.
- Discard a partial file.
- Do not persist tokens, redirect bodies, or signed URLs.
- Do not decompress, extract, or execute the bytes.
- Stop on a proxy, a non-identity content encoding, a second 401, a size or digest mismatch, or a host that was not named.

## 8. WHAT THIS BUDGET DOES NOT DECIDE

- It does not measure Python ABI, SOABI, wheel tags, or libc.
- It does not verify uncompressed rootfs diff IDs.
- It does not authenticate the publisher.
- It does not describe the final bot image or the VPS.
- It does not authorise deployment, rollback, or live trading.

## 9. VALIDATION

- Commands: git HEAD, branch, targeted status, and local JSON finalisation.
- Network requests: 0
- Files created: D.29 artifacts under data/research/adaptive_ensemble/d29/.
- Protected source, OCI objects, and reviewed D.28 and D.24-R2 files were unchanged.

## 10. FINAL CLASSIFICATION

`D29_OFFLINE_ACQUISITION_BUDGET_FINALISED`

## 11. NEXT ACTION

D.29 finalised the safety rules and the budget. It did not download a layer. It did not extract a layer. It did not execute an interpreter. It did not run Docker. It did not access production. A later acquisition still needs a separate approval that names the storage host. Production deployment is not authorised. Live trading is not authorised. Rollback is not authorised.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
