# R.80 profit protection on recovered rows

Evidence class: executed `test_16`. `profit_protection.py` hash is unchanged: `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f`.

Parameters observed by the test, not edited:

- Activation at 0.67 of the original take-profit distance. EUR and GBP triggers are 134 pips. USD_JPY trigger is 67 pips.
- ATR unavailable, so the fallback is 4.0 pips. The log line names `PROFIT_GIVEBACK_PIPS`.
- BUY uses a higher price. SELL uses a lower price. JPY pip size is 0.01.
- A stronger stored ratchet is kept.
- After `persist_protection_progress`, a real restart republishes the same protected exit pips.
- A stale epoch makes `live_management_permitted()` false. The following real cycle adds no write.

The activated row stores `protect_activated_atr_pips = 4.0` before persistence. Existing startup policy quarantines an activated row whose ATR snapshot is null. The test records the fallback that was used. It does not change the strategy.

A local or journal ratchet is not a broker-side stop modification. No TradeCRCDO, OrderReplace, or other protection adapter was added. The cycle withheld broker protection evidence because the synthetic body is incomplete.

`R80_PROFIT_PROTECTION_LIVE_ROW_VERIFIED`: PASS for the local and journal ratchet on a recovered row.
`R80_PROFIT_PROTECTION_RATCHET_PRESERVED`: PASS.
`R80_R71_PROFIT_PROTECTION_UNCHANGED`: PASS. The R.71 suite was 8 passed and the source hash matches.
Broker-side stop modification: NOT_VERIFIED.
