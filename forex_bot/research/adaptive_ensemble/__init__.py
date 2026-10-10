"""Stage G adaptive ensemble research. Offline only. EXPERIMENTAL_ADAPTIVE_ENSEMBLE_OFFLINE.

Does not reconstruct the original AI/RL bot. Does not activate strategies.
Does not import oanda_exec, bot_loop, or live-safety operator APIs.
"""

from __future__ import annotations

LABEL = "EXPERIMENTAL_ADAPTIVE_ENSEMBLE_OFFLINE"
ORIGINAL_DECISION_FIDELITY = "ORIGINAL_DECISION_NOT_REPRODUCIBLE"
STAGE_E_FAMILY = "STOP_EXPERIMENTAL_STRATEGY_FAMILY"
ORIGINAL_STRATEGIES = "KEEP_DISABLED"
PROTOCOL_ID = "stage_g_adaptive_ensemble_v1"
