"""Offline OANDA byte-bundle adapter; no downloader, authority or policy changes.

Callers supply bytes read through the existing protected Archive interface.
Hashes establish integrity against reviewed metadata, not independent authenticity.
"""
import re
from .core import PAIRS, ResearchRejected, timestamp
from .historical_sources import permission
from .historical_manifest import classify
from .historical_quality import quality
from .oanda_history_manifest import decode, digest, encoded, validated, bars
from .historical_import import SCHEMA

CONNECTIVITY_SESSION = 'd57f728a858243dca8cfc1cc39ecba44'


def import_bundle(request_bytes, manifest_bytes, raw, derivative, *, review,
                  independent_required=True):
    """Read-only conversion. Rights and first-access evidence are external review.

    The generic licensed CSV importer and all-six-instruments gate stay intact.
    This route may inspect one pair, but does not authorise strategy evaluation.
    """
    permission(review)
    if review.get('provider') != 'OANDA' or review.get('provenance_verified') is not True:
        raise ResearchRejected('oanda_provider_required')
    if review.get('manifest_sha256') != digest(manifest_bytes):
        raise ResearchRejected('reviewed_manifest_hash_required')
    request, manifest = decode(request_bytes), decode(manifest_bytes)
    spec = request.get('spec', {})
    if request.get('kind')=='BOUNDED_106':
        from .bounded_acquisition import CATALOGUE_HASH,LIMITS,spec as fixed_spec,catalogue
        catalogue()
        index=manifest.get('index')
        if (type(index) is not int or not 0<=index<106 or request.get('catalogue')!=CATALOGUE_HASH or
                request.get('limits')!=LIMITS or request.get('authorises_execution') is not False or
                manifest.get('catalogue')!=CATALOGUE_HASH or manifest.get('source')!=request.get('source') or
                type(request.get('source')) is not str or not re.fullmatch('[0-9a-f]{64}',request['source'])):
            raise ResearchRejected('bounded_catalogue_binding_refused')
        spec=fixed_spec(index)
        if manifest.get('spec_sha256')!=digest(encoded(spec)):
            raise ResearchRejected('bounded_request_hash_refused')
    pair = manifest.get('instrument')
    if (type(request.get('session')) is not str or not re.fullmatch('[0-9a-f]{32}', request['session']) or
            type(request.get('identity')) is not dict or not request['identity']):
        raise ResearchRejected('oanda_session_identity_required')
    if (pair not in PAIRS or manifest.get('synthetic') is not False or
            manifest.get('granularity') != 'M5' or
            manifest.get('request_sha256') != digest(request_bytes) or
            manifest.get('session') != request.get('session') or
            manifest.get('identity') != digest(encoded(request.get('identity'))) or
            spec.get('method') != 'GET' or spec.get('host') != 'api-fxtrade.oanda.com' or
            spec.get('path') != '/v3/instruments/' + pair + '/candles'):
        raise ResearchRejected('oanda_provenance_binding_refused')
    params = spec.get('params', {})
    if (set(params) != {'from', 'to', 'price', 'granularity', 'smooth', 'includeFirst'} or
            any(params[k] != v for k, v in
                dict(price='MBA', granularity='M5', smooth='false', includeFirst='true').items())):
        raise ResearchRejected('oanda_exact_candle_parameters_required')
    start, end = timestamp(params['from']), timestamp(params['to']) + 1
    if start != manifest.get('start') or end != manifest.get('end') or start >= end:
        raise ResearchRejected('oanda_interval_binding_refused')
    if digest(raw) != manifest.get('raw_sha256') or digest(derivative) != manifest.get('validated_sha256'):
        raise ResearchRejected('oanda_archive_hash_mismatch')
    rows, report = validated(raw, pair, start, end, manifest['retrieved'])
    if (encoded(rows) != derivative or report != manifest.get('validation') or
            len(rows) != manifest.get('observed_complete_count') or not rows):
        raise ResearchRejected('oanda_validation_receipt_mismatch')
    label = classify(start, end, review)
    if request['session'] == CONNECTIVITY_SESSION:
        label = 'PREVIOUSLY_EXAMINED_CONNECTIVITY_ONLY'
    if independent_required and label != 'INDEPENDENT_UNTOUCHED':
        raise ResearchRejected('independent_untouched_data_not_established:' + label)
    observed = bars(rows)
    q = quality(pair, observed, holiday_windows=review.get('holiday_windows', ()))
    return dict(instrument=pair, bars=observed,
                records=[dict(zip(SCHEMA, (r['time'], pair, 'true', *r['prices']))) for r in rows],
                validation=report, quality=q, independence=label,
                strategy_evaluation_permitted=False,
                evaluation_gate='Separate six-pair coverage, chronological splits and frozen V2.5 cost/portfolio checks required',
                manifest_sha256=digest(manifest_bytes))
