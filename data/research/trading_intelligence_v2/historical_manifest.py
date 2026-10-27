"""Immutable manifest validation and conservative first-evaluation exposure labels."""
import hashlib
import json
from .core import ResearchRejected,timestamp

LABELS=('PREVIOUSLY_EXAMINED','NEWLY_ACQUIRED_BUT_OVERLAPPING','INDEPENDENT_UNTOUCHED','PROVENANCE_UNVERIFIED')
KNOWN_EXPOSURE=((timestamp('2025-09-01T00:00:00Z'),timestamp('2026-10-09T07:05:00Z')),)


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def classify(start,end,record,intervals=KNOWN_EXPOSURE):
    if type(start) is not int or type(end) is not int or start>=end:
        raise ResearchRejected('invalid_coverage_interval')
    if record.get('previously_examined') is True: return LABELS[0]
    if any(start<b and end>a for a,b in intervals): return LABELS[1]
    if not (record.get('provenance_verified') is True and record.get('rights_reviewed') is True
            and record.get('research_history_complete') is True and record.get('controlled_first_access') is True
            and isinstance(record.get('independence_evidence'),str) and record['independence_evidence'].strip()):
        return LABELS[3]
    return LABELS[2]


def verify_spec(spec,expected_hash,package):
    if canonical_digest(spec)!=expected_hash: raise ResearchRejected('frozen_experiment_hash_mismatch')
    for name,expected in spec['source_hashes'].items():
        path=(package/name).resolve()
        if not path.is_relative_to(package.resolve()) or path.suffix not in ('.py','.json'):
            raise ResearchRejected('invalid_frozen_source_path')
        if hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=expected:
            raise ResearchRejected('frozen_source_changed:'+name)
    return True
