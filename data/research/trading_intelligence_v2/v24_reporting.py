"""Generate separate V2.4 findings; historical reports are never overwritten."""
import hashlib
import json


def generate(package, reconciliation, sensitivity):
    reports=package/'reports/v24'
    b=reconciliation['baseline']; w=reconciliation['waterfall']
    common='\n\nProduction remains NO-GO. Research simulation only; the 29-day archive was previously examined.\n'
    docs={
    'EXECUTIVE_SUMMARY': f'''TIV24_COST_MODEL_PARTIALLY_VERIFIED.

The original control reproduces: {b['trades']} trades, gross {b['gross']:.9f} USD,
net {b['net']:.9f} USD. No duplicate spread deduction was found. Adverse slippage
and the declared hypothetical account-currency commission reconcile independently.
No financial execution correction was justified; only opt-in observation was added.
Broker pricing is BROKER_PRICING_NOT_VERIFIED for this account. Public UK pricing
evidence is partial and differs from the existing conversion/funding assumptions.
Synthetic correctness does not establish broker execution realism.''',
    'EXECUTION_COST_TRACE': '''Call path: isolated v24_run.py -> v24_pipeline.run -> study.acquire (local archive
hash verification) -> mtf_features.prepare -> v24_engine.run -> cost_ledger.reconcile.
Existing AST adapters supply unchanged signal and protection definitions.

Signal: previous completed candle; sizing: floor the minimum of per-trade risk,
remaining portfolio risk and remaining margin capacity. Entry BUY ask + slippage,
SELL bid - slippage. Stops/targets anchor to executed entry. Holding is chronological
M5 with MTF decisions only on completed higher candles. Opening gaps precede
entries; intrabar stop precedes target when both hit; time exits use closing quotes;
software protection requests the next open.

Accounting map (source, input, unit, sign, frequency):
- engine.run entry: observed bid/ask price, quote/base, embedded spread, one fill.
- engine.close: executable exit side, quote/base, embedded spread, one fill.
- both fills: Config.slippage_pips * pip_size, quote/base, adverse once per side.
- fee_unit: commission_per_100k_side / 100000, account/base unit; entry cash debit
  once, exit cash debit once. Net trade includes both fees; cash and trade net are
  alternative representations, never sequential debits.
- close funding: entry account notional * 0.0001 * UTC dates crossed, account debit.
- Quotes.convert: signed quote P/L to account money using causal graph; no cash fee
  deducted separately. Risk uses a liability conversion at planned stop fill.
- mark: unrealised liquidation P/L minus estimated exit commission; marks do not
  mutate cash or debit a second fee.
- gross: inferred midpoint-reference movement converted with exit FX override.
- cost_account = gross - net is reporting attribution, never a cash debit.
- optional spread/slippage components likewise never change cash.

Cost trace records actual entry quotes, assumed exit quotes, fills, currency graph,
override, fees and margin. Intrabar inferred quotes are explicitly labelled.''',
    'SPREAD_ACCOUNTING': '''No second spread fee is subtracted. BUY ask entry/bid exit and SELL bid
entry/ask exit already contain spread. For flat midpoint m, units U and spreads
se,sx, quote P/L = -U*(se+sx)/2 without slippage or fees. For constant spread this
is one full spread, not two full spreads. Immediate same-candle exits still use
both executable sides; there is no synthetic spread debit.

Legacy spread_cost_account attributes U*(se+sx)/2 converted as a liability.
Because signed bid/ask conversion is nonlinear across zero, attribution need not
sum to gross-net without the small conversion residual. V24 instead uses a
sequential converted-P/L waterfall. Neither attribution is another cash charge.
Widened stress replaces the bid/ask half-width around each quoted midpoint;
it never adds another spread fee. Trigger-implied intrabar midpoint is unknown
in real ticks; the opening spread proxy cannot establish realised market spread.''',
    'SLIPPAGE_ACCOUNTING': '''Baseline 0.2 pip per fill is hypothetical: BUY entry +s, exit -s; SELL
entry -s, exit +s. s = pip_size * pips; USD_JPY uses 0.01 and other supported pairs
0.0001. It appears only in fills, never as a second cash debit. Both time and
software-protection exits use the same adverse assumption. Stops, targets and
gaps also receive one exit slippage adjustment. Stop risk includes exit slippage;
entry slippage already anchors stop geometry.

Constant adverse 0.2 or 1 pip is not an observed distribution, nor a universal
broker guarantee. UK execution policy describes both positive and negative
market-dependent slippage. See broker sources; target-gap improvement is
deliberately suppressed and gap-stop loss can exceed planned risk.''',
    'COMMISSION_ACCOUNTING': '''Config's 3 account-currency units per 100,000 base units PER SIDE is an
explicit research assumption. 10,000 units cost 0.3 on entry and 0.3 on exit,
0.6 round trip, regardless of BUY/SELL. It is not USD notional and not an OANDA
plan identification. There is no minimum commission in this model. With GBP
account it means GBP 3 per 100k side, not USD 3 silently relabelled GBP.

fee_account tests separately specified foreign-currency fees using liability
conversion; the replay's baseline commission is already in account currency.
Sensitivity B/C use zero extra commission; D retains the hypothetical baseline.
F uses a documented US rate only as a labelled non-UK comparator on these same
observed spreads, NOT a reconstruction of a core-spread feed or applicable plan.
Actual account plan, minimum fee and archive price tier remain unknown.''',
    'CURRENCY_CONVERSION': '''P/L in quote currency is sign*(exit_fill-entry_fill)*base_units. USD
accounts use identity conversion for EUR/GBP/AUD_USD quote P/L. USD_JPY/CAD/CHF
require quote-to-USD conversion; GBP accounts also require a causal GBP_USD leg.
Positive base-to-quote assets use bid, negative liabilities ask; inverse assets
divide by ask, inverse liabilities by bid. Graph edges must be <=300 seconds old
and not future. No available path rejects; no 1:1 fallback. The 300-second budget
is this M5 simulation assumption, not a broker snapshot guarantee.

Decimal independently reproduces the signed graph and all six pairs, both sides,
USD and GBP. Own-instrument conversion uses the existing execution-price override;
this is synthetic, not an independent broker conversion quote. V24 waterfall
separates spread and slippage as differences of converted P/L, avoiding false
linearity across a P/L sign change. Legacy conversion_cost_residual is an
attribution discrepancy, not a measured broker fee.

Published UK charges describe midpoint conversion with a markup for specified
subaccounts. The research signed-bid/ask conversion is not that settlement model.
Public UK financing examples use a different percentage from the charges page;
this documentary discrepancy remains unresolved. No actual account data was read.''',
    'POSITION_SIZING': '''Default account equity 10,000 and risk fraction 0.0025 give a 25 account-unit
budget. Stop distance max(2*ATR, 4*pip), target 2*stop, unchanged. Per-base-unit risk
= account liability conversion(stop_distance + exit_slip at assumed stop fill)
+ twice per-side account commission. Units=floor(min(25/risk_unit,
remaining_portfolio_risk/risk_unit, remaining_margin*leverage/notional_unit)).
Notional is liability-valued base currency in account currency. Margin=notional/20;
default allocation ceiling 80% equity, portfolio risk 2%, six positions and two
same-USD-direction slots. These are frozen research values, not account limits.

Example USD_JPY: 10,000 units * .01 = JPY 100 per pip. At bid150/ask150.02,
a JPY100 debit costs USD100/150, or GBP100/150/1.25 with GBP_USD bid1.25.
USD_CAD/CHF use .0001 times base units and their own conversion, never the JPY pip.
Tests cover all six pairs/sides/accounts and check budget and margin ceilings;
an exact EUR_USD stop oracle verifies the floor and realised loss under assumed
fill. GBP sizing is internally consistent with these hypothetical conversions,
not verified against broker markup, tier margin or account settings. Overnight
financing and gaps are not guaranteed by the intended stop-risk budget.''',
    'BROKER_PRICING_SOURCES': '''Public documentation accessed 2026-10-27; no authenticated services.

- OANDA Europe Limited / UK, forex/CFDs, retail plan not established:
  https://www.oanda.com/uk-en/trading/our-pricing/ describes liquidity-provider
  prices. Starting spreads are not historical averages or this archive's tier.
- UK v20/v20 MT4 cash settlement, home currency:
  https://www.oanda.com/uk-en/trading/our-charges/ states midpoint conversion with
  1% markup/markdown, restricted there to v20 and v20 MT4. Account applicability
  is unknown. No unverified GBP commission tariff was inferred.
- UK funding, instrument currency converted to account currency:
  https://www.oanda.com/uk-en/trading/financing-costs/ gives instrument/direction
  dependent rates and New York rollover; its worked conversion uses 0.5%, in
  conflict with the charges page. Historical applicable rates not acquired.
- UK OEL execution policy (May 2025):
  https://legal.oanda.com/?code=execution_policy_oel&language=en describes
  market-dependent slippage in either direction and volatility risks.
- US core pricing, comparator ONLY:
  https://help.oanda.com/us/en/faqs/spreads-commission.htm documents USD0.70 per
  10,000 units per leg, prorated. It is not a UK commission entitlement.
- BVI core pricing, not used in replay:
  https://help.oanda.com/bvi/en/faqs/spreads-commission.htm instead documents
  USD40/million USD notional per leg charged both upfront. Jurisdictions and
  billing bases must not be interchanged.

Public documents partly verify pricing mechanisms; actual account pricing is
BROKER_PRICING_NOT_VERIFIED. Minimum commission, guaranteed stops, platform
differences and tier eligibility remain unestablished. No claim of historical
or current user-specific tariff. No guessed financing rates were introduced.''',
    'COST_LEDGER': f'''cost_ledger.py recomputes the price arithmetic with Decimal precision 40,
independently converts quote P/L, then tests gross and net against engine outputs.
The ledger includes actual quotes/fills, inferred-quote status, currencies,
conversion book/override, fees and residual. Unknown numeric inputs reject;
unavailable conversion rejects. Full records: outputs/v24/cost_ledger.jsonl.gz
(ignored research artifact); tracked representative records: cost_ledger_examples.json.

Reconciled {reconciliation['ledger_records']} scenario-trades; maximum gross/net
residual {reconciliation['maximum_residual_account']:.12g} account units.
Absolute tolerance 1e-7 is below 0.00001 of a USD/GBP penny and permits only float
replay roundoff; it is not a trading-cost allowance.

Waterfall: converted mid-reference P/L minus spread attribution (converted gross
less converted unslipped side P/L), minus slippage attribution (unslipped side
P/L less filled P/L), minus both commissions and funding equals net. No separate
FX fee is invented. Negative controls deduct spread or commission twice and
must fail reconciliation. These tests validate the declared model, not true
contemporaneous intrabar quotes.''',
    'COST_SENSITIVITY': '''sensitivity.json contains 54 aggregate scenarios and both fold summaries:
all six unchanged strategies as M5 six-pair portfolios; trend also M15/H1/H4.
No strategy optimisation, parameter fitting or independent evaluation claim.
A: midpoint theoretical, no spread/slip/commission. B: observed bid/ask only.
C: B + hypothetical 0.2 pip per fill. D: C + hypothetical 3 account units/100k
base units per side. E: 2x observed quoted half-width, 1 pip slip, commission3.
F: same observed spreads + 0.2 pip + documented US7/100k side comparator, not UK.

Features and signals use original candles; execution quote stress changes only
bid/ask fills, triggers, conversion and capital path. Replay recomputes sizing,
eligibility and exits. Hashes identify changed entry/exit paths. Even a matching
path can resize; these comparisons are not purely additive fixed-trade debits.
Each fold starts separately at 10,000; drawdown is reported per fold and maximum
fold drawdown, never a fabricated continuous two-fold equity curve.

Break-even cost is gross account P/L / trade count on THAT realised path; negative
means no positive cost can rescue it. Not a recommendation, calibrated rate or
root of a rerun equilibrium. Financing is retained only as the labelled existing
UTC-date assumption; no broker historical funding inputs are available.''',
    'M5_LOSS_RECONCILIATION': f'''Original control was reproduced BEFORE optional trace instrumentation.
All baseline trade fields, equity and metrics match after instrumentation.

829 trades, two separate 10,000 USD folds. Legacy bridge:
gross {b['gross']:.12f}; spread {b['spread']:.12f}; slippage {b['slippage']:.12f};
commission {b['commission']:.12f}; funding {b['funding']:.12f}; conversion attribution
residual {b['conversion_residual']:.12f}; net {b['net']:.12f} USD.
gross - all five components = net, within float roundoff.

Independent waterfall: spread {w['spread_attribution_account']:.12f}, slippage
{w['slippage_attribution_account']:.12f}, commission {w['commission_account']:.12f},
funding {w['financing_account']:.12f}; net {w['net_account']:.12f}.
The two small attribution differences arise from sign-dependent FX conversion,
not an extra fee. No unexplained cash debit or changed timing is required for
this SAME-path gross/net bridge. Gross itself is conditional on cost-influenced
sizing/stops and is not the independent frictionless scenario A.

Observed-only and stressed full reruns appear below. They may alter timing,
stop/target outcomes, eligibility and units; that effect cannot be assigned to
spread alone by subtracting aggregate scenario results.''',
    'PROFIT_PROTECTION_REGRESSION': '''Operational profit_protection.py is unchanged. Existing TIV2 and MTF
regressions remain required: 67% original TP activation, ATR14*0.5, four-pip
fallback, monotonic ratchet, both sides and JPY pip precision. V24 adds a synthetic
next-open protection endpoint ledger test, which is not a substitute for those
existing source-backed tests. Cost trace is optional and does not change the
protection call, MFE update, pending flag or exit priority. No stop or target
parameter was optimised. Verification results are recorded in test_results.json.''',
    'TEST_RESULTS': '''Executable commands use python -I -S -B and the audit-isolated v24_run.py with
--v24-tests, --tests, --mtf-tests and --v23-tests. Coordinator uses its separate
offline_exposure/run_checks.py. Structured current results: test_results.json.

First V24 test run: 65 tests, four failures, zero errors/skips. Four arithmetic
fixtures unintentionally hit a four-pip stop; corrected the synthetic fixtures
to use a 20-pip stop while preserving the same expected arithmetic. No engine
behavior or safety assertion changed to satisfy them. Subsequent V24 run: 73
passed, zero failures/errors/skips. Added explicit stop, target, gap, pip-value,
margin and software-protection oracles. Double-counting negative controls reject.
One replay attempt rejected reconstructed factor-1 quotes due to float rounding; factor-1 now uses source candles unchanged. A V2.3 regression error rejected edits to its hash-pinned source; original engine.py and run.py were restored, and V24 uses separate observed copies. An AST-equivalence test strips only trace additions and requires the remaining engine to equal the frozen source. Full rerun results and hosted outcomes must be reported separately; a failing
historical full suite is never described as green.''',
    'REMAINING_LIMITATIONS': '''No independently unseen data; short archive, overlapping strategies/scenarios.
No actual user plan, jurisdiction attestation, commission minima or tier pricing.
No contemporaneous intrabar bid/ask path, order-book depth or empirical latency.
OHLC both-hit uses pessimistic stop-first; exit time upper bound is not tick time.
Opening spread proxy may misattribute intrabar costs. The synthetic execution FX
override is not independently observed broker settlement. Signed executable FX
differs from published UK midpoint markup. Financing UTC-date flat rate is not
NY rollover, holiday/weekend schedule, directional historical rate or broker fee.
GBP sizing consistency does not establish broker-realistic GBP results. No
documented commission scenario is claimed applicable to this user's account.
The US comparator retains the archive's unknown spread tier and is hypothetical
as a combined product. All adverse slippage and stress factors are assumptions.
No operational model correction, integration or live readiness is authorised.
The local bot_loop raw seal mismatch remains a separate pre-existing issue.''',
    'FINAL_DECISION': '''TIV24_COST_MODEL_PARTIALLY_VERIFIED.

Independent findings: COST_MODEL_PARTIALLY_VERIFIED; no demonstrated cash
accounting defect corrected; BROKER_PRICING_NOT_VERIFIED for the actual account.
No spread double-charge found. Declared slippage/commission are correct on both
sides. All six pair pip sizes and USD/GBP conversion/sizing are internally tested.
The reproduced M5 loss is largely spread, then hypothetical commission and
slippage. Model and pricing assumptions prevent a broker-realism certification.

Recommended next improvement: establish an explicit reviewed pricing scenario
for jurisdiction/platform/plan without credentials, and obtain approved historical
settlement/funding evidence before separately implementing a broker-specific
conversion/funding model. Preserve this baseline and make any future model a
separate version. Do not optimise the strategy to compensate for unverified fees.
Stop after V2.4. No operational integration or trading enablement.'''
    }
    selected=[r for r in sensitivity if r['strategy']=='trend' and r['timeframe']=='M5']
    details='\n\nM5 trend full-replay results (USD; gross / net / trades / max fold drawdown):\n'
    for r in selected:
        details+=f"- {r['scenario']}: {r['gross_account']:.6f} / {r['net_account']:.6f} / {r['trades']} / {r['maximum_fold_drawdown']:.6f}; baseline path matches={r['entry_exit_path_matches_baseline']}.\n"
    docs['COST_SENSITIVITY']+=details
    docs['M5_LOSS_RECONCILIATION']+=details
    for name,body in docs.items():
        (reports/('V24_'+name+'.md')).write_text('# V2.4 '+name.replace('_',' ').title()+'\n\n'+body+common,encoding='utf-8')
    hashes={p.name:hashlib.sha256(p.read_text().replace('\r\n','\n').encode()).hexdigest()
            for p in package.glob('*.py')}
    (reports/'V24_SOURCE_HASHES.txt').write_text('SHA-256 LF-normalized research text; NOT operational raw seals\n'+
        '\n'.join(k+' '+v for k,v in sorted(hashes.items()))+'\n',encoding='utf-8')
