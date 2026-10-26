# Windows procedure

This procedure does not connect to OANDA and does not ask for a token or an account identifier. Do not type either value into Cursor or into this chat.

1. Open the Start menu, type `Windows Terminal`, and open that app.
2. Go to the project folder `Forext Trading Bot 1st` on the Desktop under OneDrive.
3. Check the R.53 connector:

   `python -B -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path(r'data/research/adaptive_ensemble/r53/connector.py').read_bytes()).hexdigest())"`

   The hash must be `7e6bd27a3a65fec3e59e53771cd783c33e92d83b0ac7437a4d4caa0f37dc3df4`.
4. Check the earlier files:

   `python -B -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path(r'data/research/adaptive_ensemble/r51/https_adapter.py').read_bytes()).hexdigest())"`

   That hash must be `e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef`.

   `python -B -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path(r'data/research/adaptive_ensemble/r52/session_entry.py').read_bytes()).hexdigest())"`

   That hash must be `59cb2fab00a0a1ea67c26261571498f623e8610a8e4e55ae64ac27a3a750ac56`.

   If any hash differs, close the window.
5. Run the disabled connector:

   `python -B "data\research\adaptive_ensemble\r53\connector.py"`

6. The window must print `R53 connector is disabled. No credential prompt. No network connection.` and then exit.
7. Do not type an account identifier or a token. This program has no prompt.
8. A live program would be a later file, or a later change to this file, with a new hash that you approve in writing. The command above is not that program. `future_live_entry` only stops.
9. Before any future connection, the program would need to show the host name, the words instruments and pricing, the six pair names, and a five-second timeout. It would not show the token, the account identifier, or a full web address.
10. To abort, close the window. If a future program is waiting for a token, close it or press Ctrl+C before the token is finished.
11. The synthetic result is `data\research\adaptive_ensemble\r53\06_synthetic_output.json`. It is labelled `SYNTHETIC_TEST_ONLY`.
12. You may send back the three hash results, the disabled sentence, and the three counts if a future run exists. Do not send an account identifier, a token, a full web address, or a raw response.
