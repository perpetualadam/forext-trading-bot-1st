# Reservation safety policy

One rule is used by the database insert, the in-memory book, recovery ingest, and the broker-entry preflight.

Blocking a new client id for the same symbol:

- PENDING blocks while the reservation or execution is active.
- PARTIAL blocks while any fill or exposure from that order is still active.
- UNRESOLVED blocks until an authoritative reconciliation or terminal result that is not itself uncertain.
- Any other status, including UNKNOWN and malformed text, fails closed.

Not a reservation block:

- CANCELLED and REJECTED release the reservation hold for that symbol only. They do not release a different symbol, and they do not erase an UNRESOLVED order.
- FILLED ends the in-flight reservation hold so one historical fill does not permanently disable the symbol. FILLED does not prove the position is flat. `order_status_proves_exposure_closed` returns false for every status.

The position book is a separate gate. `bot_loop.py` returns at the open-position check before it can reserve another order. Order status alone cannot prove that a broker position is closed. No release rule was invented for that question, and no schema migration was added.

The same client id never creates a second local order. A different client id does not bypass a blocking status. A failed read, failed write, lock failure, lock timeout, deadlock, or ambiguous commit refuses the new reservation and does not mint another client id. Nothing in this repair starts a timer that releases an uncertain hold.
