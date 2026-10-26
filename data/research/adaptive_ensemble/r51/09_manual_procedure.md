# Windows procedure

This procedure does not connect to OANDA. It does not ask for a token or an account identifier. Do not type either value into Cursor or into this chat.

1. Open the Start menu, type `Windows Terminal`, and open that app. Do not use Cursor's terminal for a future credential entry.
2. Confirm the folder. The prompt should be inside `Forext Trading Bot 1st` on the Desktop under OneDrive. If it is not, change to that folder before doing anything else.
3. The reviewed isolated runner is the file `data\research\adaptive_ensemble\r51\https_adapter.py`. It is the only R.51 program. It is not the trading bot.
4. Check the file hash before trusting it. In that same window run:

   `python -B -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path(r'data/research/adaptive_ensemble/r51/https_adapter.py').read_bytes()).hexdigest())"`

   The printed hash must be exactly:

   `e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef`

   If it differs, close the window and do not continue.
5. See the disabled state. Run:

   `python -B "data\research\adaptive_ensemble\r51\https_adapter.py"`

   The window must print:

   `Live verification remains unauthorised. No credential prompt. No network connection.`

   Then the program exits. A flag, a phrase, or an environment variable does not change this.
6. A future live entry point is not in this file. After you review this stage, a later written approval would have to add a new program. Only that later program, and only after you approve its own report, would be allowed to connect. This stage does not give the command for that program, because the command does not exist.
7. In that future program, you would type the account identifier yourself in the Start-menu window, and you would type the token at a hidden prompt so the characters do not appear. You would not put either value in the command, in a file, or in chat. Hidden typing does not protect you if the computer, the terminal, a debugger, process memory, or an automated tool is already compromised.
8. Before any future connection, the program would need to show a preview with the host name `api-fxtrade.oanda.com`, the words instruments and pricing, the six pair names, a five-second timeout, and a statement that it will make two read-only reads. It must not show the token, the account identifier, or a full web address.
9. To abort now, close the window. If a future program is waiting for the token, close the window or press Ctrl+C before you finish typing. Do not continue if the hash differs or the disabled sentence does not appear.
10. A future sanitised result would include `calls_completed` of 2 and `endpoint_order` of instruments then pricing. A number other than 2 means you stop and report the number without pasting any other identifier.
11. The synthetic example of a sanitised result is `data\research\adaptive_ensemble\r51\06_synthetic_session.json`. It is labelled `SYNTHETIC_TEST_ONLY`. It is not an account reading.
12. When you report back, send the disabled sentence, the hash result, and `calls_completed` if a future run exists. Do not send an account identifier, a token, a full web address, or a raw response.

The token may be able to place trades. Broker read-only permission is unknown. Do not treat this program as a live session.
