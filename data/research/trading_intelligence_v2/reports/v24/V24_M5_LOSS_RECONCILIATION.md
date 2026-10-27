# V2.4 M5 Loss Reconciliation

Original control was reproduced BEFORE optional trace instrumentation.
All baseline trade fields, equity and metrics match after instrumentation.

829 trades, two separate 10,000 USD folds. Legacy bridge:
gross -108.118650558020; spread 3636.146318277751; slippage 938.932054537182;
commission 1521.647040000000; funding 0.000000000000; conversion attribution
residual -0.080209956369; net -6204.763853416584 USD.
gross - all five components = net, within float roundoff.

Independent waterfall: spread 3636.079079580472, slippage
938.919083278460, commission 1521.647040000000,
funding 0.000000000000; net -6204.763853416985.
The two small attribution differences arise from sign-dependent FX conversion,
not an extra fee. No unexplained cash debit or changed timing is required for
this SAME-path gross/net bridge. Gross itself is conditional on cost-influenced
sizing/stops and is not the independent frictionless scenario A.

Observed-only and stressed full reruns appear below. They may alter timing,
stop/target outcomes, eligibility and units; that effect cannot be assigned to
spread alone by subtracting aggregate scenario results.

M5 trend full-replay results (USD; gross / net / trades / max fold drawdown):
- A_MID_THEORETICAL: -377.516186 / -377.516186 / 750 / 613.334370; baseline path matches=False.
- B_OBSERVED_ONLY: -13.288709 / -4210.742405 / 807 / 2391.279123; baseline path matches=False.
- C_OBSERVED_SLIP_02: -115.493062 / -5215.846769 / 828 / 2848.304993; baseline path matches=False.
- D_HYPOTHETICAL_3_PER_100K_SIDE: -108.118651 / -6204.763853 / 829 / 3385.785489; baseline path matches=True.
- E_STRESS_2X_SPREAD_1_PIP_SIDE: 413.062049 / -15947.891039 / 1640 / 8483.189055; baseline path matches=False.
- F_US_CORE_7_COMPARATOR_NOT_UK_PLAN: -110.227224 / -7171.256312 / 830 / 3939.897527; baseline path matches=False.


Production remains NO-GO. Research simulation only; the 29-day archive was previously examined.
