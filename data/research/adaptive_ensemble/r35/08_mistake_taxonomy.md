# Mistake taxonomy

High confidence is a supplied probability of at least 0.70. The demonstration does not supply any.

Order of classification:

1. `invalid_prediction` when the prediction status is invalid.
2. `unevaluable_outcome` when the future bar is missing or misaligned.
3. `insufficient_information` when no prediction exists.
4. `missed_opportunity` when an abstention has a positive hypothetical cost-adjusted result on either side.
5. `correct_abstention` for the other abstentions.
6. `high_confidence_incorrect` or `incorrect_directional_prediction` when the side does not match the midpoint move.
7. `correct_direction_negative_cost` when the side matches and the cost-adjusted result is negative.
8. `low_confidence_correct` when the side matches, the cost-adjusted result is not negative, and confidence is below 0.70.
9. `not_a_classified_mistake` when a high-confidence directional call matches and the cost-adjusted result is not negative.

A loss is not automatically a model mistake. A gain is not automatically a good prediction.

Log loss and Brier score are implemented only for probabilities the caller supplies. A missing probability map returns `unavailable`. Calibration, class balance, abstention coverage, and regime slices are specified for R.36 and were not computed.
