# R.75 Universal Close Guard Contract

## Authority object

`CloseSubmissionPermit` (`close_journal.py` lines 117–122) is a value copied from a committed journal row. Constructing one in the caller does not authorise a close. There is no `skip_guard` and no `already_verified` argument.

`issue_submission_permit` (lines 351–368) returns a permit only when `submission_authorized` is true: intent is 1, `network_permit` is 0, the owner token matches, confirmation is `CLOSE_SUBMITTING`, and submission state is `SENDING`.

## Final boundary

`_submit_position_close_body` (`oanda_exec.py` lines 401–415) does this before `get_api` and before `api.request`:

1. Reject the argument unless it is a `CloseSubmissionPermit`.
2. Call `claim_network_permit`.
3. On `JournalUnavailable`, raise `CloseGuardRefusal`.

`claim_network_permit` (lines 370–414) runs one `BEGIN IMMEDIATE` update that sets `network_permit=1` and `submission_state='SENT'` only when all of these match the row:

- operation id
- owner token
- account binding
- instrument
- trade id
- direction
- requested units
- position-instance id
- position generation
- submission intent 1
- `network_permit` still 0
- confirmation state `CLOSE_SUBMITTING`

`rowcount` must be 1. Any other result rolls back and raises `submission_authority_refused`. A second claim, a stale token, or a mismatched field commits nothing and no HTTP request is made.

`_place_market_order_sync` (line 462) and `execute_oanda_market_close` (line 676) require the same permit argument. They have no default.

## Caller contract

`run_guarded_live_close` persists the bot position, reserves, commits intent, issues the permit, checks the owner token and the in-memory identity, then passes the permit into `_submit_position_close_body`. `CloseGuardRefusal` is stored as `CLOSE_RECONCILIATION_REQUIRED` / `submission_authority_refused` / `NOT_SENT`. It is not treated as an ambiguous sent request.

`execute_trade` with kind `live` raises `RuntimeError` at `trading.py` line 392 and does not mint a journal operation.

## Failure of the client after a successful claim

If the claim commits and `get_api()` then returns None, `RuntimeError` is raised after the permit is consumed (`oanda_exec.py` lines 416–418). The operation cannot be claimed again. That is fail-closed. It can leave a close unsent. It does not authorise a fallback submission.
