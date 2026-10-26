# Windows procedure

This procedure does not connect to OANDA and does not ask for a token or an account identifier. Do not type either value into Cursor or into this chat.

1. Open the Start menu, type `Windows Terminal`, and open that app. Do not use Cursor's terminal for a future credential entry.
2. Go to the project folder `Forext Trading Bot 1st` on the Desktop under OneDrive. The window's path should end in that folder before you continue.
3. Check the R.52 entry point. Run:

   `python -B -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path(r'data/research/adaptive_ensemble/r52/session_entry.py').read_bytes()).hexdigest())"`

   The hash must be exactly:

   `59cb2fab00a0a1ea67c26261571498f623e8610a8e4e55ae64ac27a3a750ac56`

4. Check the R.51 adapter. Run:

   `python -B -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path(r'data/research/adaptive_ensemble/r51/https_adapter.py').read_bytes()).hexdigest())"`

   The hash must be exactly:

   `e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef`

   If either hash differs, close the window.
5. Start the disabled entry point:

   `python -B "data\research\adaptive_ensemble\r52\session_entry.py"`

6. The window must print:

   `R52 entry point is disabled. No credential prompt. No network connection.`

   Then it exits. A flag or an environment variable does not change this sentence.
7. Do not type an account identifier or a token after that sentence. This stage has no prompt, and a value typed here would not be a protected credential entry.
8. A live session needs a later written approval after you review the R.52 report. That later change must publish a new hash. The hashes above are for the disabled program only.
9. A future approved program would ask `Account identifier: ` and then `API token: ` with the token hidden. It would show the host name, the words instruments and pricing, and the six pair names before any connection. It would not show a full web address. That prompt is not available in this program.
10. To abort, close the window. If a future program is waiting, close the window or press Ctrl+C before the token is finished.
11. The synthetic sanitised example is `data\research\adaptive_ensemble\r52\06_synthetic_output.json`. It is labelled `SYNTHETIC_TEST_ONLY`. It is not an account reading.
12. You may send back the two hash results, the disabled sentence, and `calls_completed` if a future run exists. Do not send an account identifier, a token, a full web address, or a raw response.

The token may be able to place trades. Broker read-only permission is unknown.
