# Gate G — margin and spread requirements

MARGIN SOURCE MISSING. SPREAD POLICY UNAPPROVED. No leverage, margin percentage, or numeric spread cap was invented.

## Margin evidence required before any future production seal

- Account id bound to the order, from an authenticated AccountSummary, not a caller field.
- Environment label and an explicit GBP spread-betting compatibility result. That check does not exist.
- Account currency.
- NAV kept distinct from available margin.
- `marginAvailable`, which the summary parser already names but the entry path does not read.
- `marginUsed`, which is not parsed.
- Margin closeout status, which is not parsed.
- Required margin for the candidate order, from the broker, including instrument currency conversion when the account currency differs.
- Existing position margin, from the broker position book rather than the local book.
- A snapshot timestamp and an acquisition timestamp. The current summary has neither.
- Stale or missing margin evidence must remain a mandatory block. Equity is not margin proof.

Until those fields exist, the standing gate `margin` stays `NOT_IMPLEMENTED`.

## Spread evidence required before any future production seal

- Instrument price precision from the existing `pip_size` helper, not a new table.
- Bid, ask, broker quote time, and local acquisition time, bound to the same order intent.
- An approved maximum-spread policy source that states whether the limit varies by instrument or session.
- Unknown or absent policy remains `POLICY_UNAPPROVED`.
- The order-entry price, the spread bid/ask, and the broker `entry_quote` argument must be the same bound quote. Today sizing uses `dependencies.price` and the shared adapter request leaves `entry_quote` empty. That split must be closed in a later stage before a production seal, not by inventing a threshold now.
