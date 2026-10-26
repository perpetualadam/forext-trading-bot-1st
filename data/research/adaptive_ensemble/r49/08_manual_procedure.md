# How a future connection would be run

Do not do the entry steps in this section now. R.49 does not approve them. The program as built will not ask for a token and will not connect.

If you run it today, from any window, it should print: "R49 handoff is prepared. Network gate is closed. No credential prompt." Then it stops. That is the safe result. Do not type a token after that line.

## What must be true before a later session

A later instruction has to approve this procedure in writing. Until that exists, stop here.

The later run has to be started by you, outside Cursor. Cursor's own terminal is not a safe place to type the token. Hidden typing does not keep a secret away from Cursor, a recorder, or another program that can see the process.

The token may be able to place trades. A GET-only program does not remove that ability. This project has not confirmed a broker setting that limits the token to reading.

## Later steps, only after that approval

1. Close Cursor, or at least do not use its terminal. Press the Windows key, type `Windows Terminal`, and open that app from the Start menu. PowerShell from the Start menu is the same kind of window. Do not open the terminal from inside Cursor.
2. Go to the project folder. The program to run, when a later build actually prompts, is `data\research\adaptive_ensemble\r49\handoff_runner.py`. Do not run `main.py`.
3. The window would ask for the account identifier. Type it and press Enter. The characters may not appear. That is expected. Do not put the identifier in the command you use to start the program.
4. The window would then ask for the API token in the same hidden way. Do not put the token in the command, in a file, or in chat.
5. The program checks that both entries exist. It does not print them back. If either entry is empty, it stops with `R49_INPUT_REJECTED`.
6. It would build only two read requests, for the six currency names, on the live OANDA host. One request is the instrument list. The other is a single price snapshot with home-currency conversion. It would not send orders.
7. It would not print the full web address, the token, or the raw reply. A result that still contained the secret would not be saved.
8. It would make those requests once and then exit. It would not keep asking and it would not keep a copy of the token.
9. You would open the saved research file and check that it names the six instruments and their public contract fields, and that your account identifier is not in it.
10. To abort before any connection, close the window, or press Ctrl+C, before you finish the hidden prompts. Closing the window is enough.

## If the window cannot be trusted

Do not type the token. Close the window. That includes Cursor, a shared screen, a recorded terminal, or any window that might be copied by an assistant. If a token was typed in the wrong place, revoke it yourself on OANDA's own site. Do not paste it into chat while you do that.

There is no new saved password store. Do not create one.
