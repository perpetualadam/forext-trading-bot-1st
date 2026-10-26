# Windows procedure

This procedure does not connect to OANDA and does not ask for a token or an account identifier. Do not type either value into Cursor or into this chat.

1. Open the Start menu, type `Windows Terminal`, and open that app.
2. Go to the project folder `Forext Trading Bot 1st` on the Desktop under OneDrive.
3. Check the R.55 session file:

   `python -B -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path(r'data/research/adaptive_ensemble/r55/session_main.py').read_bytes()).hexdigest())"`

   The hash must be `5913a190812343a9039570893f6cc96fb30fb2a08a6305b84e0bb7bea3576cf8`.
4. Check the imported dependency files:

   `python -B -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path(r'data/research/adaptive_ensemble/r51/https_adapter.py').read_bytes()).hexdigest())"`

   That hash must be `e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef`.

   `python -B -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path(r'data/research/adaptive_ensemble/r52/session_entry.py').read_bytes()).hexdigest())"`

   That hash must be `59cb2fab00a0a1ea67c26261571498f623e8610a8e4e55ae64ac27a3a750ac56`.

   `python -B -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path(r'data/research/adaptive_ensemble/r53/connector.py').read_bytes()).hexdigest())"`

   That hash must be `7e6bd27a3a65fec3e59e53771cd783c33e92d83b0ac7437a4d4caa0f37dc3df4`.

   `python -B -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path(r'data/research/adaptive_ensemble/r54/session_main.py').read_bytes()).hexdigest())"`

   That hash must be `50d2dfd2b3c7e2909994e7ccbebfd30d7c50021e8a2a8f70df5f11d78b880280`.

   If any hash differs, close the window.
5. Run the disabled entry point:

   `python -B "data\research\adaptive_ensemble\r55\session_main.py"`

6. The window must print `R55 session is disabled. No credential prompt. No network connection.` and then exit.
7. Do not type an account identifier or a token. This program has no prompt. Boundary A does not include a live session.
8. A live program would be a later file, or a later change to this file, with a new hash that you approve in writing after reading this procedure. The command above is not that program. `future_live_entry` only stops.
9. Before any future connection, the program would need to show `api-fxtrade.oanda.com`, GET, instruments then pricing, the six pairs `EUR_USD`, `GBP_USD`, `AUD_USD`, `USD_CAD`, `USD_CHF`, and `USD_JPY`, a maximum of two requests, a five-second timeout, certificate verification, redirects disabled, retries disabled, trading actions prohibited, unknown token permission, account home currency not yet API-verified, and spread-bet stake semantics not yet verified. It would not show the token, the account identifier, a full web address, or an authorization header.
10. The future program would then wait for a local confirmation of that preview. A refusal stops the program.
11. Only after that confirmation would a future approved program ask for the account identifier and then the token with hidden input. This procedure does not ask you to do that.
12. To abort, close the window. If a future program is showing the preview or waiting for a token, close it or press Ctrl+C before the token is finished. No request should be sent after that.
13. The synthetic result is `data\research\adaptive_ensemble\r55\06_synthetic_output.json`. It is labelled `SYNTHETIC_TEST_ONLY`. It is not broker data.
14. You may send back the five hash results and the disabled sentence. Do not send an account identifier, a token, a full web address, an authorization header, or a raw response.
