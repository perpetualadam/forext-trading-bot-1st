"""Non-authorising V2.8A planning and offline reconciliation. No I/O or execution."""
from dataclasses import dataclass
import re
from .core import ResearchRejected, timestamp, iso
from .oanda_history_manifest import encoded, decode, digest
from .oanda_research_import import import_bundle

START = timestamp('2024-08-05T00:00:00Z')
END = timestamp('2024-08-12T00:00:00Z')
IDS = ('109f365402a844adacad671d62e4458f',
       'b2e5582e3cd347bd80a02109d7a476c2',
       '5d4e7676ab9e4393a4678cfb23274a4c')


@dataclass(frozen=True)
class Window:
    session: str
    start: int
    end: int
    source: str

    @property
    def spec(self):
        return dict(method='GET', host='api-fxtrade.oanda.com',
                    path='/v3/instruments/EUR_USD/candles',
                    params=dict(granularity='M5', price='MBA', smooth='false',
                                includeFirst='true', **{'from': iso(self.start),
                                                       'to': iso(self.end - 1)}))

    @property
    def maximum_candles(self):
        return (self.end - self.start) // 300

    @property
    def destination(self):
        return 'C:\\TradingResearchData\\OANDA\\sessions\\' + self.session


def plan(source, ids=IDS):
    """Proposals only. Never creates a namespace, grant or next-session approval."""
    if (type(source) is not str or not re.fullmatch('[0-9a-f]{64}', source) or
            type(ids) is not tuple or len(ids) != 3 or len(set(ids)) != 3 or
            any(type(x) is not str or not re.fullmatch('[0-9a-f]{32}', x) for x in ids)):
        raise ResearchRejected('pilot_plan_identity_refused')
    return tuple(Window(session, START + i * 1000 * 300,
                        min(END, START + (i + 1) * 1000 * 300), source)
                 for i, session in enumerate(ids))


def merge_completed(source, bundles):
    """Reconcile three completed byte bundles, never execute the next request.

    Each bundle has request/manifest/raw/validated/journal/result/claimed_grant
    bytes and a separately reviewed V2.8 rights/provenance record. Use existing
    protected Archive readers to obtain bytes; this function never opens files.
    """
    return merge_window_bundles(source, plan(source), bundles, start=START, end=END,
                                classification='PILOT_ONLY_NOT_INDEPENDENT_EVALUATION')


def merge_window_bundles(source, windows, bundles, *, start, end, classification):
    """Offline reuse for a fixed caller-reviewed plan; never grants authority.

    Existing rights/provenance import and durable DONE/single-use checks remain
    mandatory for every batch. Unknown coverage is reported, never repaired.
    """
    if not windows or windows[0].start != start or windows[-1].end != end:
        raise ResearchRejected('merge_plan_coverage_refused')
    if len({w.session for w in windows}) != len(windows):
        raise ResearchRejected('merge_plan_duplicate_session')
    for i, w in enumerate(windows):
        if (w.source != source or w.start % 300 or w.end % 300 or
                not 0 < w.end-w.start <= 1000*300 or
                i and windows[i-1].end != w.start):
            raise ResearchRejected('merge_plan_boundary_refused')
    if type(bundles) is not tuple or len(bundles) != len(windows):
        raise ResearchRejected('three_completed_pilot_batches_required' if len(windows)==3 else 'all_completed_planned_batches_required')
    records, reports, seen = [], [], set()
    for window, bundle in zip(windows, bundles):
        request, journal, result = (decode(bundle[k]) for k in ('request', 'journal', 'result'))
        if (request.get('session') != window.session or request.get('source') != source or
                request.get('spec') != window.spec or
                journal.get('session') != window.session or journal.get('state') != 'SESSION_CONSUMED' or
                journal.get('attempts') != 1 or result.get('session') != window.session or
                result.get('source') != source or result.get('kind') != 'DONE' or
                result.get('journal_state') != 'SESSION_CONSUMED' or result.get('attempts') != 1 or
                result.get('worker_exited') is not True or
                result.get('grant_sha256') != digest(bundle['claimed_grant'])):
            raise ResearchRejected('pilot_completed_session_binding_required')
        grant = decode(bundle['claimed_grant'])
        if (grant.get('session') != window.session or grant.get('source') != source or
                grant.get('spec') != digest(encoded(window.spec))):
            raise ResearchRejected('pilot_cross_session_authority_refused')
        imported = import_bundle(bundle['request'], bundle['manifest'], bundle['raw'],
                                 bundle['validated'], review=bundle['review'], independent_required=False)
        for row in imported['records']:
            t = timestamp(row['time'])
            if t in seen:
                raise ResearchRejected('pilot_duplicate_timestamp')
            if not window.start <= t < window.end or records and t <= timestamp(records[-1]['time']):
                raise ResearchRejected('pilot_boundary_or_order_refused')
            seen.add(t)
            records.append(row)
        reports.append(imported['validation'])
    # Record every missing run, including edges and cross-batch gaps. Do not
    # infer a holiday or a forex session calendar from the weekday alone.
    gaps, begin = [], None
    for t in range(start, end + 300, 300):
        missing = t < end and t not in seen
        if missing and begin is None:
            begin = t
        if not missing and begin is not None:
            gaps.append(dict(start=iso(begin), end=iso(t), missing_candles=(t - begin) // 300,
                             kind='MISSING_SESSION_OR_CLOSURE_NOT_ESTABLISHED'))
            begin = None
    return dict(records=records, count=len(records), expected_calendar_slots=(end-start)//300,
                missing_intervals=gaps, batch_validation=reports,
                independence=classification,
                strategy_evaluation_permitted=False, authorises_execution=False)
