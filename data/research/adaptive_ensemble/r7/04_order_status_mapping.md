# Order status mapping

| Word | database.py | orders.py | bot_loop.py |
| --- | --- | --- | --- |
| PENDING | Insert status. Recovery loads it. | `OrderStatus.PENDING` | Reservation before send |
| PARTIAL | Recovery loads it. Fill update can write it. | `OrderStatus.PARTIAL` | Not a new entry |
| FILLED | Fill update | `OrderStatus.FILLED` | After a confirmed fill |
| CANCELLED | Cancel update, except it will not overwrite UNRESOLVED | `OrderStatus.CANCELLED` | Confirmed cancel, and pre-send failures |
| REJECTED | Not a stored word by itself | Not an enum value | Confirmed rejection calls the cancel path |
| UNRESOLVED | Stored by `persist_unresolved_order`. Recovery loads it. | `OrderStatus.UNRESOLVED` | Ambiguous and unknown send errors |

Unknown text is not turned into PENDING. `ingest_recovery_snapshot` raises and sets the fail-closed flag.

SOURCE-REVIEWED. Not engine-tested.
