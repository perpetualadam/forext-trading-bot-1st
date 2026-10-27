"""V2.5 evidence reports, kept separate from every earlier research version."""
import hashlib
import json


def generate(package,summary):
    reports=package/'reports/v25'
    rows=summary['results']
    base=[r for r in rows if r['strategy']=='trend' and not r['protection']]
    example=[r for r in base if r['timeframe']=='M5' and r['pricing']=='OBSERVED_BID_ASK_ONLY']
    lines='\n'.join(f"- {r['policy']}: trades {r['trades']}, net {r['net_account']:.6f} USD, net/trade {r['net_expectancy'] if r['net_expectancy'] is not None else 'undefined'}, max fold drawdown {r['maximum_fold_drawdown']:.6f}; rejected baseline winners {r['candidates'].get('opportunity_rejected_winners',0)}, avoided baseline losers {r['candidates'].get('opportunity_avoided_losers',0)}." for r in example)
    original=next(r for r in base if r['timeframe']=='M5' and r['pricing']=='HYPOTHETICAL_BASELINE')
    improved=[]
    for r in base:
        if r['policy']=='A_BASELINE': continue
        a=next(x for x in base if x['pricing']==r['pricing'] and x['timeframe']==r['timeframe'] and x['policy']=='A_BASELINE')
        improved.append(dict(pricing=r['pricing'],timeframe=r['timeframe'],policy=r['policy'],
            net_expectancy_difference=(r['net_expectancy']-a['net_expectancy']) if r['net_expectancy'] is not None and a['net_expectancy'] is not None else None,
            net_portfolio_difference=r['net_account']-a['net_account']))
    (reports/'paired_effects.json').write_text(json.dumps(improved,indent=2,allow_nan=False)+'\n')
    eligible=[r for r in improved if r['policy']!='E_EXACT_VOTES']
    better_e=sum(r['net_expectancy_difference'] is not None and r['net_expectancy_difference']>0 for r in eligible)
    better_p=sum(r['net_portfolio_difference']>0 for r in eligible)
    freq=next(r for r in example if r['policy']=='A_BASELINE')['frequency']
    cohorts=[r for r in summary['quality_bins'] if r['strategy']=='trend' and r['timeframe']=='M5' and r['pricing']=='OBSERVED_BID_ASK_ONLY']
    grouped={}
    for r in cohorts:
        key=(r['field'],r['value'])
        group=grouped.setdefault(key,dict(trades=0,net=0,gross=0))
        group['trades']+=r['trades'];group['net']+=r['net_account'];group['gross']+=r['gross_account']
    context='\n'.join(f"- {k[0]}={k[1]}: {v['trades']} trades, net {v['net']:.6f}, gross {v['gross']:.6f} USD; net/trade {v['net']/v['trades']:.6f}." for k,v in sorted(grouped.items()) if v['trades'])
    docs={
    'EXECUTIVE_SUMMARY': f'''TIV25_COST_AWARE_RESEARCH_PARTIALLY_VERIFIED.

Implemented a causal research-only evaluator, fixed policies and entire portfolio
replays. No production strategy or broker execution is changed. No new independent
data was acquired and the user's actual broker plan remains unknown. Thresholds
were frozen before V25 replay, but design is informed by prior examined history.
No optimisation, policy selection or confidence calibration used this archive.

Across the 24 B/C/D timeframe-pricing diagnostic comparisons, {better_e} have
higher sample net expectancy and {better_p} higher portfolio net P/L than A.
These are correlated descriptive comparisons, not success rates or independent
evidence. E removes no trades: no exact redundant entry predicates were proven.
F and the adaptive selector abstain without fresh validation.

M5 observed-only diagnostic results:\n{lines}''',
    'BROKER_PRICING_ASSUMPTIONS': '''The V24 source review was inspected; public UK charges were rechecked
2026-10-27: https://www.oanda.com/uk-en/trading/our-charges/ . Public documents
cannot identify the user's jurisdiction, account type, pricing plan, account
currency or entitlement. No credentials or authenticated broker data were read.
No US commission rate is treated as a UK plan.

OBSERVED_BID_ASK_ONLY: existing observed bid/ask, zero extra commission/slippage.
This is an archive diagnostic, not a broker-pricing applicability certification.
HYPOTHETICAL_STRESS: same observed spreads plus 0.5 pip adverse per actual fill
and 3 account units per 100k base units per side. This rate is unverified.
HYPOTHETICAL_BASELINE: original 0.2 pip/side plus commission3, unchanged control.
DOCUMENTED_SPREAD_ONLY and DOCUMENTED_COMMISSION_PLAN are supported by the
evaluator only with explicit applicability; both are disabled in this study.
Pricing is never chosen using performance. All portfolio runs are USD; GBP
pre-entry conversion is synthetic-tested, not presented as verified GBP pricing.

V24's signed bid/ask FX conversion and UTC-date financing remain hypothetical.
The cost estimate assumes intraday flattening and no estimated funding; it does
not promise broker rollover avoidance or calculate undocumented financing.
Current-spread persistence is an estimate, not a known future exit spread.''',
    'DATA_COVERAGE': '''No independent historical dataset was acquired. Existing V23 importer and
source-permission checks were inspected. Public provider documentation was
rechecked 2026-10-27; no archive was downloaded:
- FXCM: https://github.com/fxcm/MarketData/blob/master/CandleData/README.md ;
  personal-use archive subject to EULA; applicable project rights unresolved.
- Dukascopy Europe: https://www.dukascopy.com/europe/english/legal-pages/terms-of-use/ ;
  project database-use permission not established.
The user's earlier clarification confirms no FXCM permission. No protected
service was scraped, no EULA form submitted and no broker API contacted.

Only the 29-trading-day previously examined six-pair M5 archive was replayed,
with study.acquire verifying existing provenance hashes. Exact source provenance,
aggregation gaps and fold times are in ignored outputs/v25/input_manifest.json.
Earlier local 12-month candles were previously examined and lack the required
verified acquisition chain; they are not relabelled independent data.

Missing prerequisite: >=12 months (prefer24–36) M5 or finer observed bid/ask for
EUR_USD, GBP_USD, USD_JPY, AUD_USD, USD_CAD, USD_CHF, reviewed automated-use and
derived-publication rights, provider identity, UTC/completion conventions, original
hashes, gap/duplicate/precision checks, full research-exposure review and controlled
first access. The V23 importer remains the ingestion contract; no fabricated asks.''',
    'DECISION_ENGINE': '''decision_quality.Request carries instrument, side, decision/feature/quote
times, explicit completion, current bid/ask, ATR, stop/target, horizon, units,
pricing, account, strategy, regime, volatility/momentum and completed context.
Evaluator returns ACCEPT, REJECT_COST, REJECT_RISK, REJECT_DATA, REJECT_SIGNAL
or ABSTAIN_UNCERTAIN with reason, inputs and metric trace. No probability is
assigned and no realised outcome is accepted as input.

Inputs reject missing/nonfinite quotes/ATR, nonpositive ATR, crossed/stale/future
quotes, incomplete/future/stale features, invalid geometry/capacity or unavailable
FX conversion. Quotes have the existing research 300-second maximum age; features
must be available within the current M5 decision interval. Context uses actual
completed M15/H1/H4 timestamps, never an unfinished candle. Documented pricing
without applicability abstains; explicit hypothetical scenarios remain labelled.

v25_adapter.Evaluator constructs requests at the research engine hook after
baseline sizing/constraints and before entry acceptance. Existing constraints
retain precedence. Baseline A and E are verified against the frozen V24 replay's
metrics, equity and every trade field except new decision metadata. Frequency
annotations are recorded on copies, never on engine state.''',
    'COST_OPPORTUNITY': '''For units U, current spread a-b, pip p, per-side assumed slippage s pips:
spread quote debit=U*(a-b), slip quote debit=2*U*s*p. Convert each liability with
V24's independent Decimal converter and add two explicit account-currency fees.
Do not debit these estimates from replay cash: actual bid/ask fills already
contain spread. Execution P/L still reconciles through the V24 cost ledger.

spread_pips=(a-b)/p; spread_ATR=(a-b)/ATR; spread_stop=(a-b)/stop_distance;
spread_target=(a-b)/target_distance. cost_R=estimated_account_cost divided by
spot liability value of stop_distance*U; cost_target uses target_distance*U.
This price-only R denominator is labelled separately from engine initial risk,
which includes planned exit slippage, commissions and stop-price FX.

Illustrative binary MID-REFERENCE payoff: win +T, lose -S, fixed cost C each trade.
Break-even win rate=(S+C)/(S+T); >1 means unattainable under that assumed payoff.
It is not a forecast probability and not the engine's fill-anchored target payoff.
Target is intended geometry, not expected movement; expected_gross_movement=None.
Current-spread and spot FX estimates may differ from exit costs. Future realised
MFE, MAE, returns, spread or FX cannot affect a decision.''',
    'FREQUENCY_DIAGNOSIS': f'''M5 observed-only baseline counts:\n{json.dumps(freq,indent=2)}

Frequency means candidate signals as well as actual entries; signals while a
position exists are not multiple executed trades. Records flag repeated direction,
adjacent M5 signals, existing-position rejection, <=one-M5-bar reentry after an
exit and stop reentry. That one-bar interval is descriptive, never a cooldown.
Counts are available by instrument, strategy, timeframe, session, regime,
volatility, weekday and current spread/ATR condition; durations and USD turnover
use executed trades. Six M5 standalone-strategy baseline portfolios provide
frequency diagnostics, not six independent diversification streams.

V23's near-99.42% scalp/trend active agreement remains prior descriptive evidence;
different predicates are not deduplicated merely because directions agree.
unique_votes consolidates only identical predicate identity, instrument, time
and side. E supplies one pinned-strategy predicate per candidate, so E is exactly
baseline-equivalent; no independent opportunity is suppressed. Correlated signals
are not counted as independent statistical observations. Neither repeated counts
nor cost savings alone establish excessive economic trading frequency.''',
    'ENTRY_QUALITY': f'''Pre-entry cohorts on actually executed M5 observed-only trend entries:\n{context}

These overlapping cohorts describe conditional sample outcomes, not causal
causes or a trained classifier. Costs, directional movement, exits and capital
path interact. Weak momentum, low/high volatility and context conflict are
recorded causal metadata; no probability or profitable condition was inferred.
Complete per-fold cohort records: entry_quality.json; per-entry cost inputs and
counterfactuals: ignored outputs/v25/decision_records.jsonl.gz.

Every policy candidate is paired by instrument/time/side to the baseline action.
Executed baseline trades retain their full baseline trade record. No baseline
trade means outcome UNKNOWN_UNEXECUTED_BASELINE, never zero or assumed loser.
Rejected winners and losers are both counted. Matching baseline outcomes cannot
measure opportunity cost for trades baseline never executed.''',
    'POLICY_COMPARISON': f'''Small fixed hypothesis set, not a parameter grid:
A unchanged baseline; B spread/ATR<=0.25; C estimated cost/target<=0.25;
D all completed M15/H1/H4 trend states agree with entry; E exact-vote consolidation.
Both quarter-budget thresholds are illustrative, frozen before first V25 replay,
informed by prior research, not independent calibration or optimal parameters.
No alternative thresholds were tried. F combined policy remains disabled without
fresh training/validation support. No archive-fitted threshold or selector exists.

M5 observed-only:\n{lines}

policy_comparison.json contains accepted entries, rejected candidates and reasons,
acceptance rates, avoided baseline losers/rejected winners, unknown counterfactuals,
gross/net expectancy, R, PF, win rate, drawdown, total net/cost, exposure and turnover.
It labels candidate rejection separately from an executed trade. Rejections can
change all subsequent capacity, sizing and outcomes: every case replays its entire
portfolio, never subtracts rejected P/L from A. Full fold/by-instrument/session/
regime/duration diagnostics are in outputs/v25/full_summary.json.''',
    'ADAPTIVE_SELECTION': '''Actual adaptive result: ABSTAIN_NO_FRESH_INDEPENDENT_TRAINING_VALIDATION.
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
not demonstrate adaptive performance on unseen market data.''',
    'WALK_FORWARD': '''Same original two chronological nonoverlapping test windows for every
paired diagnostic; exact times are in the input manifest. Features retain causal
warm-up and completed higher candles. Each test fold starts at10,000 USD with
identical frozen research risk/capacity constraints; source candles and execution
assumptions are identical within pricing comparisons. Fixed policies require no
fitting. Prior train/validation labels do not make this known archive unseen.

No fresh untouched final holdout exists. The selector's separate purged lifecycle
is synthetic-tested only; it was NOT applied as a fitted model to these folds.
Portfolio daily outcomes are paired by calendar date; bootstrap stays within fold
boundaries. Drawdown is maximum within separately started folds, never a falsely
continuous account. No test outcomes change thresholds or selected rules.''',
    'PORTFOLIO_RESULTS': f'''Full-replay M5 observed-only comparison:\n{lines}

Original V24 cost control reproduced: {original['trades']} trades,
gross {original['gross_account']:.9f}, net {original['net_account']:.9f} USD.
The report includes four entry timeframes and two explicitly labelled cost
conditions, with fixed A profit-protection comparisons. Other five M5 strategies
are unfiltered frequency controls only, not optimised policy candidates.
Full source-backed portfolio paths include cash, margin, risk, same-USD-direction
capacity, stop-first ambiguity and exit timing. Avoided losers alone do not
establish an improvement; rejected winners and newly available trades matter.
Some lower activity can reduce losses without producing positive expectancy.''',
    'STATISTICAL_ASSESSMENT': f'''32 fixed B/C/D/E versus A paired daily portfolio comparisons: two pricing
cases * four entry timeframes * four policies. Reuse existing two-day moving-block
bootstrap,2,000 draws, seed25; fold boundaries retained. Holm family includes all32
even unavailable estimates. All reliable_advantage_established flags remain false.
Machine-readable effect intervals, raw/adjusted values and fold-day counts are
in performance.json; expectancy and portfolio effect sizes in paired_effects.json.

{better_e}/24 B/C/D comparisons have higher sample net/trade, {better_p}/24 higher
sample total net. Counting these is descriptive, not a binomial success test:
strategies, pairs, policies and pricing cases overlap. Short nonstationary known
data cannot validate block length, symmetry or IID trade assumptions. Paired
trade outcomes are not used as independent samples. No minimum-count, positive
sample score or adjusted p-value permits promotion or a claim of unseen edge.''',
    'PROFIT_PROTECTION_REGRESSION': '''forex_bot/profit_protection.py is unchanged. The actual existing source
is reused through Existing:67% original TP-distance activation, ATR14*0.5,
four-pip fallback, monotonic ratchet, BUY/SELL and JPY pip precision. No parameters
were optimised. Fixed baseline protection-on comparisons were replayed under
both pricing cases across all four entry timeframes; no protection variant was
selected by its result. Earlier source-backed suites and V25 engine equivalence
checks are required and recorded in test_results.json. There are no broker
trailing stops, breakeven amendments or partial closes.''',
    'TEST_RESULTS': '''Run python -I -S -B data/research/trading_intelligence_v2/v25_run.py
--v25-tests. Executable tests cover cost formulas and units, BUY/SELL and JPY,
GBP conversion, malformed/stale/future inputs, completed context, frozen policies,
abstention, duplicate votes, clustering/reentry, rejected winners/losers/unknowns,
baseline equivalence, changed portfolio availability, selection isolation,
deterministic hashes and denied network/journal/enablement access.
Negative controls intentionally double a cost expectation or supply lookahead
and require rejection. No financial outcome assertion was weakened.
An initial replay computed the scenarios but failed on a missing report-renderer import while that new module was still being created. The failed-attempt summary was retained in ignored outputs, and the complete pipeline was rerun. Current executed regression and cross-platform results: test_results.json.
Replay provenance, reproducibility and source preservation: verification.json.
Hosted verification is recorded separately after publication; overall CI must
not be described as green when the historical full-suite job fails.''',
    'INTEGRATION_STATUS': f'''Explicit research call path: v25_run.py --v25-evaluate -> v25_pipeline ->
v25_engine decision_evaluator hook -> v25_adapter -> decision_quality.evaluate.
The hook is after baseline constraints/sizing and before entry acceptance;
it adds no authority and does not bypass existing rejection. Decision records,
baseline counterfactuals, costs, trades and independent V24 ledgers are emitted.
Baseline A/E comparisons are checked against the unchanged V24 replay.

All older source/report files remain preserved; v25_engine is a separate observed
research copy. An AST-boundary test removes only the optional hook and requires
identity to V24. No operational strategy selection, broker execution, position
ownership, recovery, permit, gate or production state is integrated or changed.
Records={summary['ledger_records']} reconciled trades, maximum accounting residual
{summary['max_ledger_residual']:.12g}; record digest {summary['records_sha256']}.
Production integration is disabled and unapproved.''',
    'REMAINING_LIMITATIONS': '''No independent12-month bid/ask dataset or applicable account pricing.
The old archive informed the design, so freezing V25 hypotheses is not a cure
for historical selection bias. No threshold optimality or unseen advantage.
Current-spread/spot-FX cost estimates are proxies; target is not an expected move.
V24 intrabar spread, signed-conversion, financing and constant-slippage limitations
remain. Higher candle gaps and warm-up cause abstention; UTC H4 is a research
alignment, not a certified broker session. Rejected unexecuted baseline signals
have unknown counterfactual outcomes. Correlated votes need predicate identity,
not directional agreement, to justify suppression. No arbitrary cooldown is used.
Adaptive selection has only synthetic lifecycle evidence. No tested change yet
has sufficient market/pricing evidence for operational promotion.''',
    'FINAL_DECISION': '''TIV25_COST_AWARE_RESEARCH_PARTIALLY_VERIFIED.

The software supports causal cost-aware decisions and reproducible full-path
comparisons. Diagnostic improvements are conditional samples; they do not prove
that lower frequency, higher net/trade or higher total P/L will persist. Both
weak gross directional/exit outcomes and cost burden remain plausible contributors;
repeated signal frequency alone cannot distinguish them causally.

No evidence establishes adaptive outperformance on genuinely unseen data.
No policy is sufficiently supported for operational integration. Recommended next
stage: secure reviewed bid/ask research rights, provenance and controlled first
access for >=12 months, establish applicable pricing assumptions, then evaluate
this already frozen policy set with purged train/validation and untouched final
holdout. Do not tune these thresholds on the29-day diagnostic archive.
Stop after V2.5. Production remains NO-GO.'''
    }
    for name,text in docs.items():
        (reports/('V25_'+name+'.md')).write_text('# V2.5 '+name.replace('_',' ').title()+'\n\n'+text+
            '\n\nResearch only. Production remains NO-GO.\n',encoding='utf-8')
    hashes={p.name:hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in package.glob('*.py')}
    (reports/'V25_SOURCE_HASHES.txt').write_text('SHA-256 LF-normalized research source; operational raw seals are separate\n'+
        '\n'.join(k+' '+v for k,v in sorted(hashes.items()))+'\n',encoding='utf-8')
