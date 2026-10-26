# R.43 protected-holdout design

No holdout was opened or evaluated in R.43. No local file qualifies as a protected holdout.

## Partitions

- Development-only: the six-pair M5 and M1 files from 2025-09-01 through 2026-08-31, plus any feature, swing, or regime output already computed from them.
- Previously inspected, not a holdout: the G.3 M5 extract from 2026-09-01 through 2026-10-09.
- Future development slice: the first portion of a later acquisition, chosen by timestamp before any strategy looks at it.
- Final holdout: the later portion of that same acquisition. Instruments and the cut time are written into the protocol before the first development read.

A holdout that is one short overlapping sample of the same six USD pairs is still one correlated sample. It is not six independent trials.

## Access

- Development code may read the development slice and the exposed year.
- The final holdout may be read by one evaluation run after the protocol hash is stored.
- Feature discovery, threshold search, and model training may not read the holdout.
- A failed or rejected strategy stays rejected. It is not revised and run again on the same holdout.
- A second look at the same holdout is recorded as a repeated test, not as a new independent result.
- Any change to the feature definition, the cost model, the instrument list, or the cut time after the protocol hash invalidates a claim of independence.
- The R.42 range definition stays frozen. Holdout results are not a reason to widen the reach rule.

## Unlock

The holdout unlocks only when a later authorisation names the protocol hash, the cut time, and the single evaluation script. R.43 does not create that authorisation.
