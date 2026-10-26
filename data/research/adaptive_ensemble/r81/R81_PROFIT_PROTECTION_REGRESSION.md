# R.81 profit-protection regression

`forex_bot/profit_protection.py` was not edited. Hash `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f`.

`test_16` executes the unchanged helpers: EUR pip size 0.0001, JPY pip size 0.01, EUR trigger 134 pips, JPY trigger 67 pips, and a stored 12-pip ratchet that does not fall to a weaker candidate. No broker stop adapter was added.

The R.71 suite and the R.80 recovered-row integration are rerun with the historical files. Their counts are in the Windows and Linux result reports. A journal ratchet is not a broker-side stop modification.

`R81_RECOVERED_PROFIT_PROTECTION_UNCHANGED`: PASS for the hash and the executed parameter check. The recovered-row cycle remains the R.80 test, which this stage reruns rather than rewrites.
