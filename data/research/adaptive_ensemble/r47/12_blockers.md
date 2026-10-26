# R.47 remaining blockers

The sizing specification is written. The GBP risk engine is not implemented. The account contract is not fully verified. Practice and live orders stay blocked.

| Blocker | Class | Why it remains |
| --- | --- | --- |
| API meaning of one unit | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` | The ticket shows a units heading and rejects a £1-per-pip reading. It does not show the order body. |
| Unrounded GBP pip value | `UNKNOWN` | 0.00 GBP is a two-decimal display. |
| Minimum and increment | `UNKNOWN` | Quantity 1 was not submitted. |
| Conversion markup | `CONFLICTING_EVIDENCE` | GBP labels agree with the profile. The rate was not shown. Code paths still disagree. |
| Margin rate | `UNKNOWN` | 0.03 GBP does not identify it. Rounding modes disagree about whether 3.33% is inside the band. |
| Closeout | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` | Not on the ticket. Not applied in the bot. |
| Stop distance and guaranteed stop | `UNKNOWN` | Normal and the two input labels only. |
| Financing | `UNKNOWN` | Fail-closed, with no rate. |
| Other five pairs | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` | No ticket. |
| Fill currency | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` | No fill exists for this unsubmitted ticket. |
| Positive size clamp | `LOCALLY_VERIFIED_IMPLEMENTATION` | Default `MAX_POSITION_UNITS` does not clamp. Not changed here. |
| USD production path | `CONFLICTING_EVIDENCE` | Still approximate USD against a GBP ticket. |

A repeated photograph at two-decimal precision cannot remove the pip-value blocker.
