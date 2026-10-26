# R.49 synthetic tests

No real token was used. No connection was opened.

## Attempt 1

2 failed, 4 passed.

The source scan rejected the runner because the result used the key name `requests`. That is the same word as the banned HTTP library. The scan stayed. The empty-input check also failed its assertion because an empty string is contained in every error sentence. The input was still rejected with `R49_INPUT_REJECTED`.

## Attempt 2

6 passed.

The result key is now `planned_calls`. The source scan still forbids `requests`, `forex_bot`, `getenv`, `urllib`, `socket`, and `.env`. Empty, blank, and newline inputs are still rejected. The empty-input assertion no longer treats an empty string as a leaked secret.

Covered on the passing run: no production import, no environment read, no `.env` access, no HTTP library, GET-only plans, the fixed live host, fixed path patterns, argument rejection, redirect and retry flags left closed, no request body, no stream, a 5-second timeout on the plan, account-identifier and token redaction, no `Bearer` or `Authorization` text in the result, no full URL in the result, no file written when a secret would be stored, missing and malformed payloads rejected, and the confirmation phrase still leaving the network gate closed. The default process prints that the gate is closed and does not prompt.
