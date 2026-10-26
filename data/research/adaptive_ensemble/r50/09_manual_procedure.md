# Proposed Windows procedure

This procedure does not connect to OANDA. It does not ask for a token or an account identifier.

1. Leave Cursor's terminal unused for credentials. Do not paste a token into chat.
2. Open a normal Windows PowerShell window from the Start menu only if you want to see the offline message.
3. Go to the project folder `Forext Trading Bot 1st`.
4. Run `python -B "data\research\adaptive_ensemble\r50\connector.py"`.
5. The window prints: `Live verification remains unauthorised. No credential prompt. No network connection.`
6. The program then exits. Adding a flag, a phrase, or an environment variable does not open a connection. There is no network client in this program.
7. Do not edit `connector.py` to force a connection. A later stage has to add that client under a new written authorisation.
8. Close the window.
9. If a token was typed into Cursor, a recorder, or a chat, revoke that token on the OANDA website yourself. Do not paste the token here to ask whether it was exposed.

A future authorised session, which this stage does not start, would still be limited to two GET requests for the six instruments, in a window opened from the Start menu, with the token typed once and never written to a file.
