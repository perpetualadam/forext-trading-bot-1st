# Entry-point architecture

`session_entry.py` loads the pinned R.51 adapter, which loads the R.50 connector and the R.48 gate. It does not import a production package or a third-party HTTP client.

Normal execution calls `launch`. That function checks the R.51 pin, prints the disabled sentence, and returns. It does not call credential entry, the connection factory, or the live session.

`run_synthetic` accepts an in-memory credential and an injected factory, then calls the R.51 two-read workflow. The result is reduced to an allowlisted document before it can be written. Validation failure writes nothing.

`live_session` raises `R52_LIVE_TRANSPORT_DISABLED` as its first action. No argument, environment variable, or confirmation phrase is consulted. There is no boolean that turns the live path on.

The future activation is a later change to this file, or a new file, with a new published hash. This hash does not include that activation.
