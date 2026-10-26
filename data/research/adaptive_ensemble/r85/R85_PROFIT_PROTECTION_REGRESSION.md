# R.85 Profit Protection Regression

Evidence: file hash and the durable ratchet column. `forex_bot/profit_protection.py` was not edited.

SHA-256 remains `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f`.

The source still contains the 0.67 trigger default and the 0.5 ATR multiplier default. ATR(14), the four-pip fallback, the monotonic ratchet, BUY/SELL handling, JPY pip size, original SL/TP, and weekend flattening were not modified.

Executed fixture: `profit_protection_exit_pips` stored as 40 and read back as 40 after a partial close and a restart onto a 600-unit snapshot. The restart did not clear it. No stop-replacement request was in the synthetic write set. No automatic close and no re-entry were submitted.

A lower ratchet was not written. The existing `persist_protection_progress` refusal of a backward ratchet was not changed and was not re-tested as a new mutation. The stored value simply stayed 40.

This does not verify a broker-side stop.
