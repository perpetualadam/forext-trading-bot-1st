# V2.4 Slippage Accounting

Baseline 0.2 pip per fill is hypothetical: BUY entry +s, exit -s; SELL
entry -s, exit +s. s = pip_size * pips; USD_JPY uses 0.01 and other supported pairs
0.0001. It appears only in fills, never as a second cash debit. Both time and
software-protection exits use the same adverse assumption. Stops, targets and
gaps also receive one exit slippage adjustment. Stop risk includes exit slippage;
entry slippage already anchors stop geometry.

Constant adverse 0.2 or 1 pip is not an observed distribution, nor a universal
broker guarantee. UK execution policy describes both positive and negative
market-dependent slippage. See broker sources; target-gap improvement is
deliberately suppressed and gap-stop loss can exceed planned risk.

Production remains NO-GO. Research simulation only; the 29-day archive was previously examined.
