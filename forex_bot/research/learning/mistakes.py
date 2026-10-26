"""Research mistake labels. A losing outcome is not automatically a model mistake."""

from __future__ import annotations

import math

from forex_bot.research.learning.protocol import HIGH_CONFIDENCE

CLASSES = frozenset(
    {
        "incorrect_directional_prediction",
        "correct_direction_negative_cost",
        "low_confidence_correct",
        "high_confidence_incorrect",
        "correct_abstention",
        "missed_opportunity",
        "insufficient_information",
        "invalid_prediction",
        "unevaluable_outcome",
        "not_a_classified_mistake",
    }
)


def classify_mistake(row: dict) -> str:
    """Classify one explicit row. Missing confidence is not filled in."""
    status = row.get("prediction_status")
    if status == "invalid":
        return "invalid_prediction"
    if not row.get("outcome_evaluable"):
        return "unevaluable_outcome"
    if status in (None, "unavailable"):
        return "insufficient_information"
    if status == "abstain":
        best = row.get("best_hypothetical_cost_return")
        if best is not None and math.isfinite(float(best)) and float(best) > 0.0:
            return "missed_opportunity"
        return "correct_abstention"
    if status != "directional":
        return "invalid_prediction"
    direction = row.get("direction")
    move = row.get("directional_outcome")
    matched = (direction == "BUY" and move == "up") or (direction == "SELL" and move == "down")
    confidence = row.get("confidence")
    if not matched:
        if confidence is not None and math.isfinite(float(confidence)) and float(confidence) >= HIGH_CONFIDENCE:
            return "high_confidence_incorrect"
        return "incorrect_directional_prediction"
    cost = row.get("cost_adjusted_return")
    if cost is not None and math.isfinite(float(cost)) and float(cost) < 0.0:
        return "correct_direction_negative_cost"
    if confidence is None or not math.isfinite(float(confidence)):
        return "insufficient_information"
    if float(confidence) < HIGH_CONFIDENCE:
        return "low_confidence_correct"
    return "not_a_classified_mistake"


def probabilistic_scores(probabilities: dict | None, outcome: str | None) -> dict:
    """Score supplied probabilities. A missing prediction stays unavailable."""
    if probabilities is None or outcome not in probabilities:
        return {"status": "unavailable", "log_loss": None, "brier_score": None}
    probability = float(probabilities[outcome])
    if probability <= 0.0 or probability > 1.0:
        return {"status": "invalid", "log_loss": None, "brier_score": None}
    others = [float(value) for key, value in probabilities.items() if key != outcome]
    brier = (probability - 1.0) ** 2 + sum(value ** 2 for value in others)
    return {"status": "computed", "log_loss": -math.log(probability), "brier_score": brier}
