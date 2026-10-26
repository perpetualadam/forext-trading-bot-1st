# Blank-direction source trace

The live side is chosen in `forex_bot/bot_loop.py` lines 1176-1178:

```
direction = str(ai_decision.get("direction", "BUY")).upper().strip()
if direction not in ("BUY", "SELL"):
    direction = "BUY"
```

Those three lines were executed in isolation, using the text from the file. `_evaluate_impl` was not called.

Missing key: the `.get` default is already `"BUY"`.
None, `""`, `" "`, `"NO_TRADE"`, `"UNKNOWN"`, `0`, and `1` all fail the BUY/SELL test and are replaced with BUY.
`"BUY"` and `"buy"` stay BUY. `"SELL"` and `"sell"` stay SELL.

This code is reached only after candle load, the live-permission check, an active and authorised strategy, and an AI vote with `allow` true (`bot_loop.py` 1144-1165). None of those earlier steps were run. An AI result that is not a dict, or that has `allow` false, returns earlier and does not reach this coercion.

There is no NO TRADE value after this point. An unrecognised direction becomes BUY.
