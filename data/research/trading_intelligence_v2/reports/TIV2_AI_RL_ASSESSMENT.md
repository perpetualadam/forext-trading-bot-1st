# AI and RL ablations

{
  "ai": {
    "allow": false,
    "confidence": 0.0,
    "direction": null,
    "status": "unavailable",
    "reason": "no_voters"
  },
  "rl": "UNAVAILABLE",
  "quant_stub": {
    "allow": false,
    "confidence": 0.0,
    "direction": null,
    "status": "unavailable",
    "reason": "quant_stub_removed"
  },
  "model_artifact": "UNAVAILABLE: no fold-bound verified model loaded",
  "calibrated_probabilities": false
}

Quantitative shadow alone and +regime have executed replays. +AI, +RL and combined strict gates all abstain (zero approved trades; expectancy undefined), because no fold-bound trained, verified, calibrated model was supplied. The actual empty AI ensemble returns no_voters, retired quant stub returns quant_stub_removed, and RLAgent without persisted_ok returns UNAVAILABLE. This does not prove no production model exists: production stores and credentials were intentionally not accessed. Persistence code exists in decision_repair/rl_store.py; existence of its schema does not establish this study has a trained leakage-free policy. No external voter/API calls, model training, invented predictions or confidence calibration claims. Measurable incremental AI/RL value: not established.

Status: TIV2_OFFLINE_RESEARCH_PARTIALLY_VERIFIED. Production remains NO-GO. All results are hypothetical archived-data replay, never broker fills. The 29-day archive and short OOS windows do not establish statistical significance or live profitability.
