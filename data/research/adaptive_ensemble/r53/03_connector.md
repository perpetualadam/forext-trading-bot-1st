# Connector

`connector.py` loads the R.50 request builder and the R.48 parsers by file path. It does not import a production package.

`launch` checks the prior hashes, prints the disabled sentence, and returns. It does not prompt and it does not call the transport.

`run_synthetic` accepts an in-memory credential and an injected client class. It sends instruments, validates that response, then sends pricing only if instruments validated. A failure stops the session. The three counts are kept separately: `requests_attempted`, `successful_http_responses`, and `validated_sanitised_responses`.

`future_live_entry` raises `R53_LIVE_TRANSPORT_DISABLED` before any other work. No flag, phrase, environment variable, or boolean is read as an on switch. A live session needs a later approval and a new hash.

Output is accepted only when its keys match an explicit allowlist. `write_clean` writes a file only when both endpoints validated. Any other document is refused and no file is created.
