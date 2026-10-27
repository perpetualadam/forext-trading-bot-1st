# V2.6 Data Validation

Strict JSON rejects duplicate keys, nonstandard NaN/Infinity and unexpected
response/candle fields. Require exact instrument, M5, explicit boolean completion,
integer volume and all observed mid/bid/ask OHLC components. Finite positive
decimal strings allow at most12 fractional digits; original lexemes are retained,
never rounded to a guessed display precision. Instrument precision metadata is
not fetched, so this lexical ceiling is a research validation policy.

Require low<=open/close<=high and comparable bid<=ask. Timestamps normalize to
UTC, must align M5, and reject nonzero fractional nanoseconds rather than truncate.
Reject duplicate/disordered/out-of-range candles before publication. Incomplete
candles are counted and excluded; completed timestamps must precede retrieval.
No sorting, deduplication, interpolation, invented asks or silent invalid-row repair.

Every missing run, including empty windows, is recorded. Weekend-containing gaps
are not certified closures; holiday/calendar evidence remains unknown. No empty
response establishes requested historical completeness. Invalid raw/error bodies
are not archived because arbitrary unexpected fields could echo credentials.
Only validated candle-schema responses become raw evidence. Synthetic checks
exercise gaps, weekends, cross quotes, malformed OHLC and incomplete exclusion.

Production remains NO-GO.
