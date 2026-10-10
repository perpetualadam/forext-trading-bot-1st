"""Offline Stage F decision-engine repairs. All features default OFF.

These modules do not activate strategies, grant live-order authorisation,
or open broker orders. Trading effectiveness of the deterministic selector
is ``UNVALIDATED``.
"""

from __future__ import annotations

POLICY_VERSION = "deterministic_rotate_v2_unvalidated"
POLICY_EFFECTIVENESS = "UNVALIDATED"
RL_SCHEMA_VERSION = 1
AUDIT_SCHEMA_VERSION = 3
HEALTH_SCHEMA_VERSION = 1
RISK_SCHEMA_VERSION = 2
CURSOR_SCHEMA_VERSION = 1
RESULT_LABEL = "STAGE_F_ENGINEERING_REPAIR"
F1_RESULT_LABEL = "STAGE_F1_ENGINEERING_COMPLETION"
F2_RESULT_LABEL = "STAGE_F2_ENGINEERING_HARDENING"
