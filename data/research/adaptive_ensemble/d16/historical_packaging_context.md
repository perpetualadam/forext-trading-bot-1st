# Historical packaging context

Historical hashes are context only. They do not identify the current working tree.

- G.7 frozen source SHA: `0ee97accd2d4a8297a053eb26c5138324192ab5b1f700214acf091d0f6487f82`
- G.7 manifest SHA: `ba8eb86d887b44dd44314c6a45c776639bf11bb27f0e92ba2ce24978c3206989`
- G.10 source snapshot SHA: `d0317de858a00b194bc44408932ad6508eec411fe0179b0196175a2985b12277`
- G.10 manifest SHA: `93c73c21bd6f144e7d656be74128a771c3274025c0e88b8a052ffbc742f417cf`
- G.10 allowlist SHA: `b2d0f66f8a696da5488072720f6d8de7ceccfd8c847d54327d4cfff2e10eb7b4`
- G.14.1 file count: 63
- G.14.1 manifest SHA: `8597768f9b351ee5a8b8c3750cb4df12880a25414dfb4e6aab072e1fe2b3b33b`

The G.14.1 staging directory was not opened and was not recreated.

The checked-in G.10 allowlist records an older `Dockerfile` hash `f8d537d84c8ab004c5fc2cbdc5ef58e8141f5ca66a13be6cc5eac38c7c7006a6` and an older `app.py` hash. The current Dockerfile hash is `4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad`. The current `.dockerignore` hash matches the G.10 record. Current source bytes are therefore not the G.10 package.
