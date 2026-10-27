# V2.5 Adaptive Selection

Actual adaptive result: ABSTAIN_NO_FRESH_INDEPENDENT_TRAINING_VALIDATION.
Combined policy: DISABLED_NO_FRESH_VALIDATION. No policy was fitted or selected
using the previously examined archive; no zero-trade abstention portfolio is
presented as a successful trading policy.

cost_aware_policies.fit_selector has an executable synthetic lifecycle: immutable
chronological Split, >=16-hour purge between phases (longest 4*H4 horizon), only
completed/available train and validation outcomes, minimum30 samples in each,
positive mean minus two standard errors in each, then deterministic validation
ranking and a frozen context map. These are explicit research eligibility
heuristics, not significance or independent-observation guarantees. Rejects test
rows, future outcomes and duplicate outcomes. Missing independent-data evidence
or no eligible policy yields abstention. Attestations alone cannot establish
provider rights, provenance or genuine independence. Synthetic selection does
not demonstrate adaptive performance on unseen market data.

Research only. Production remains NO-GO.
