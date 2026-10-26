# Two-cycle offline trace

These cycles are synthetic. They are not authorised production trades. Production eligibility stayed false, and the production adapter was not used.

## FILLED hold

Cycle 1 at 2026-01-07T12:00:00+00:00 consumed snapshot `EUR_USD|ask|1.0999500000|1.1000500000|2026-01-07T12:00:00+00:00|2026-01-07T11:58:00+00:00|50`.
Bid 1.09995 and ask 1.10005 were the same quote used for the spread, for BUY sizing at the ask (1.10005), and for the entry quote.
The selector executed and its selected name was mean_reversion. That result controlled the iteration (`mean_reversion`). The AI vote was {'allow': True, 'direction': 'BUY'}. The RL decision was BUY.
Accepted equity was 10000.0. The inert adapter was called 1 time. The recorded order cid-507a6296fa4148efa08aa6f7f779a015 is FILLED.
Spread policy was POLICY_UNAPPROVED. Margin evidence was NOT_IMPLEMENTED. Production eligibility was False.
The fill left an unconfirmed exposure hold and a local position. It was not treated as flat.

Cycle 2 at 2026-01-07T12:01:00+00:00 was offered bid 1.1 and ask 1.1001. It did not build a snapshot, because the existing hold stopped it first.
Before any new decision it read exposure `exposure_unconfirmed` and found the local position still open.
It stopped with `position_already_open` before strategy selection, reservation, and dispatch. Inert calls: 0. Broker calls: 0.

## UNRESOLVED hold

Cycle 1 called the inert adapter 1 time and received `ambiguous`.
The order was not retried. Exposure after the attempt was `exposure_unconfirmed`. No broker-flat release was written.

Cycle 2 read that hold and stopped with `exposure_unconfirmed`.
Reservation attempted: False. Inert calls: 0. Broker calls: 0.

The local order status after the ambiguous attempt is UNRESOLVED. The process also records an unresolved intent and an unconfirmed exposure hold. Those three facts describe the same uncertain attempt. This is not a broker reconciliation.
