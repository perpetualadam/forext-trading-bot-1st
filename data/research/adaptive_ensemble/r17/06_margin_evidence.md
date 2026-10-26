# Margin evidence

The account snapshot has no margin-available, margin-used, margin-closeout, or instrument-margin field that this stage can treat as a policy. No margin rate, leverage, financing cost, or available-funds rule was added.

On the shared path, after the accepted equity is frozen:

- `margin_evidence` is `not_implemented`.
- `margin_sufficiency` is `NOT_EVALUATED`.
- `equity_is_not_margin_proof` is true.

A positive balance, a payload field named `marginAvailable`, a negative number, a non-finite number, or a currency string does not become a margin pass. Broker margin sufficiency remains NOT_EVALUATED (I182).
