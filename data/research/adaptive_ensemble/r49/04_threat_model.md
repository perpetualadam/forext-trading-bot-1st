# R.49 threat model

The values to protect are the API token and the account identifier. The token may be able to trade. The following are the ways they could leak, and the control this build uses.

| Exposure | Control in this build | Limit of the control |
| --- | --- | --- |
| Cursor chat or the AI context | The procedure forbids pasting either value here. | A person can still paste them. The program cannot stop that. |
| Command-line arguments | `main` rejects every argument and prints only `R49_INPUT_REJECTED`. | A different program could still be started with the token. Do not do that. |
| Source code and configuration files | The runner contains no token and no account identifier. There is no new store. | Do not edit the file to insert them. |
| Logs and evidence | Errors use fixed sentences. Output is refused if it contains the secret, `Bearer`, `Authorization`, or `https://`. | A crash dump outside this program is not covered. |
| Git history | This stage's files contain no secret. | Do not commit a token later. |
| Production imports | The runner does not import `forex_bot`. | Importing the production client would read the existing environment and `.env`. |
| Other processes and memory | The secret would exist in the runner's memory only during a future entry. | Hidden typing does not stop a debugger, a recorder, or another process from reading that memory. |
| Cursor's terminal and tools | The current program does not ask for a secret. | If a future run happens inside Cursor, the agent and the terminal log may see the session. That is not an approved place to type the token. |

`getpass` hides the characters on a normal console. It does not guarantee that the secret stays outside Cursor, an IDE recorder, a terminal history tool, or process memory. This stage does not claim that it does.
