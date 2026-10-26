# R.86 Snapshot Pagination

Evidence: source inspection of `fetch_broker_positions_detail` and executed `assess_supplied_pages`. No pagination client was added.

`OpenPositions` is constructed once, with an account id and no page parameter. The interpreter walks one `positions` list. There is no next-page field, page-size limit, or loop guard on this path.

`oanda_account_adapter` can see transaction `pages` on an injected document and treats pages without transactions as incomplete. That is a different document. It was not connected to the position snapshot.

Caller-supplied page records, which the adapter does not produce, were evaluated:

| Case | Result |
| --- | --- |
| Missing middle page | `INCOMPLETE`, reason `missing_page` |
| Missing final page | `INCOMPLETE`, reason `missing_page` |
| Repeated page token | `INCOMPLETE`, reason `repeated_page` |
| Duplicate trade | `INCOMPLETE`, reason `duplicate_trade` |
| Failure after a page | `FAILED` |
| Mixed accounts | `FAILED`, reason `mixed_account` |
| Unexpected token | `INCOMPLETE` |
| Pagination loop | `INCOMPLETE` |
| Two well-formed pages | `UNKNOWN_COMPLETENESS`, not verified |

A multi-page complete fixture is not supported. Two well-formed supplied pages stay unknown. Empty observations stay unverified. Pagination completion for the live position endpoint remains unverified.
