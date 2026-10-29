"""V2.8B exact offline request plan. No issuer, client, credential or filesystem I/O."""
import re
import uuid
from .core import timestamp, iso, ResearchRejected
from .oanda_history import Plan
from .oanda_history_manifest import encoded, digest
from .historical_manifest import classify
from .pilot_history import Window, merge_window_bundles

START = timestamp('2024-09-01T00:00:00Z')
END = timestamp('2025-09-01T00:00:00Z')
NAMESPACE = uuid.UUID('ac0ac642-6fc9-4adf-a65b-dd429f9af1fd')


def plan(source):
    if type(source) is not str or not re.fullmatch('[0-9a-f]{64}', source):
        raise ResearchRejected('reviewed_source_seal_required')
    fixed = Plan(START, END, instruments=('EUR_USD',), environment='live', batch_candles=1000)
    return tuple(Window(uuid.uuid5(NAMESPACE, 'V28B:'+source+':'+str(a)+':'+str(b)).hex,
                        a, b, source) for _, a, b in fixed.batches())


def request_plan(source):
    windows = plan(source)
    records = [dict(number=i+1, start=iso(w.start), end_exclusive=iso(w.end),
                    request_id=w.session, instrument='EUR_USD', specification=w.spec,
                    spec_sha256=digest(encoded(w.spec)), maximum_candles=w.maximum_candles,
                    source_seal=source, source_seal_role='REFERENCE_ONLY_NOT_LIVE_AUTHORITY',
                    archive_destination=w.destination,
                    predecessor=None if i==0 else windows[i-1].session,
                    predecessor_requirement='Fresh separate approval' if i==0 else
                        'All preceding planned sessions DONE, consumed, one attempt, worker exited, hashes/source/identity verified; fresh separate approval still required',
                    completion_state='PLANNED_NOT_AUTHORISED', authorises_execution=False)
               for i,w in enumerate(windows)]
    return dict(version='V28B_OFFLINE_PLAN_1', start=iso(START), end_exclusive=iso(END),
                request_count=len(records), calendar_slots=(END-START)//300,
                maximum_future_attempts_after_separate_approval=len(records),
                currently_authorised_attempts=0, live_scope_supported=False,
                retries=0, redirects=False, proxies=False, pagination=False, fallback=False,
                source_seal=source, source_seal_role='Existing pilot implementation reference; LIVE catalogue does not include these windows',
                authorises_execution=False, windows_sha256=digest(encoded(records)), windows=records)


def independence(review):
    """Dates outside known exposure do not establish a complete history review."""
    return classify(START, END, review)


def merge_completed_year(source, bundles):
    """Existing offline merger/importer checks; no download or partial completion.

    Expanded rights evidence must bind each new manifest. Pilot-only evidence
    cannot pass the existing per-manifest hash gate. No evaluation is enabled.
    """
    return merge_window_bundles(source, plan(source), bundles, start=START, end=END,
                                classification='YEAR_DATA_REQUIRES_SEPARATE_INDEPENDENCE_REVIEW')
