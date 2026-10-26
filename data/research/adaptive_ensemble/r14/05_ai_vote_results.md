# AI vote

ACTUAL AI VOTE EXECUTED.

The shared path calls `AIEnsemble.vote`. A supplied response goes through `_SuppliedVoter.predict` and then the real aggregation. A missing confidence is filled only so the existing wrapper can read the field. That is not a replacement algorithm.

Valid BUY and SELL reach the fake broker once when the strategy flag, RL agreement, sizing, and reservation also pass. A no-trade vote, a missing vote, a malformed object, a swallowed voter exception, a swallowed timeout, and a non-finite aggregate confidence all stop before the fake broker.

An empty ensemble returns `allow=False` and `direction=BUY`. The shared path rejects it because `allow` is false. There is no BUY order from that fallback.

A supplied direction that is not BUY or SELL is rejected by the canonical gate even if the ensemble tie-break would rewrite it to BUY.

No model weights were trained or written.
