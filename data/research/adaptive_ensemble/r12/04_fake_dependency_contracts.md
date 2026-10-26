# Fake dependency contracts

All fakes live in `tests/r12_fakes.py` and the test process.

- Candles are synthetic dictionaries. No download and no production market file.
- The clock is a fixed `datetime`. The seam rejects a missing clock instead of calling `utcnow`.
- The vote is an injected dictionary. `ai.vote` is not called.
- Strategy active and authorised flags are arguments. The six production strategy objects stay inactive.
- The account balance is an injected number. A missing snapshot uses `current_equity` and records that the source has no separate snapshot gate.
- Reservation uses the existing in-memory order book with `PERSIST_EXEC_ORDERS=0`. No PostgreSQL connection is opened.
- `FakeBroker.submit` appends one request and returns a scripted response: accepted, filled, partial, rejected, refused, timeout, connection failure, ambiguous, malformed, duplicate, or conflicting quantity. It has no OANDA client.
- A simulated request is a recorded test event. It is not an authorised order.
- The seam closes the fake broker in a `finally` block, including when `submit` raises.
