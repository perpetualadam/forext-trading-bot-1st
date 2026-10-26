# R.49 standalone architecture

The runner is `data/research/adaptive_ensemble/r49/handoff_runner.py`. It uses the Python standard library and the R.48 research gate. It does not import `forex_bot`, does not use a production HTTP session, and does not contain an order call or an HTTP client.

`NETWORK_EXECUTION` is false. `arm_network` requires the phrase `APPROVE PHASE B` and then still raises `R49_NETWORK_GATE_CLOSED`. A correct phrase does not open a connection in this build.

Default execution prints one status line and exits. It does not prompt. It does not read the environment. It does not read `.env`.

A hidden prompt function exists for a later approved run. This build never calls it. Tests supply synthetic values through a stand-in reader.

Injected synthetic responses can be parsed into the sanitised schema. The account identifier is used only to check the path shape in memory. It is not copied into the result. The token is checked for presence and then dropped. Unexpected response fields are dropped. A document that still contains a secret is not written.

Phase B, the real connection, is not implemented. Adding the HTTPS call requires a later explicit approval. This file must not be edited to flip the gate as part of R.49.
