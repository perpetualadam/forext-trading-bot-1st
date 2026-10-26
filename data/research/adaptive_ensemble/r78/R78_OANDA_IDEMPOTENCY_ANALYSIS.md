# R.78 OANDA idempotency analysis

Classification: `BROKER_IDEMPOTENCY_NOT_DOCUMENTED`

Also retained: `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`

The question was whether OANDA v20 documents an enforceable guarantee that submitting the same client order identifier twice cannot create two distinct trades.

The Order Endpoints page shows `clientExtensions.id`, `tag`, and `comment` on a create request. It shows `OrderSpecifier` accepting `@` plus that client id for a later GET. It shows a sample where `my_order_100` is the client id and `6373` or `6375` is the OANDA order id.

The Transaction Definitions page says `OrderFillTransaction.clientOrderID` is present only when the client assigned one. It does not say the broker rejects a second create that repeats it.

No sentence on the retrieved pages says that `clientExtensions.id` is an idempotency key, that a duplicate POST returns the original order, or that a duplicate POST cannot open a second trade. A sample response is not that guarantee.

`tag` and `comment` are client-supplied annotations in the same example. They are not identifiers and are not documented as uniqueness constraints.

The local journal remains the retry barrier. `one_client_order_id` and `client_order_id_registry` keep a client id after reservation. `begin_entry_submission` raises `unresolved_entry_exists` for an in-flight row and `client_order_id_retained` once the id is in the registry. No automatic resubmit was added.

A timeout after a synthetic or real acceptance stays ambiguous. The investigation classifier returns `no_matching_evidence` with reason `absence_is_not_rejection` when a complete snapshot has no matching client id. That result sets `retry_permitted` false.
