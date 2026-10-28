"""Non-authorising review boundary. No issuer, grant writer or live switch.

Replacing this refusal requires a separately reviewed implementation and approval.
Python access control does not protect against deliberately modified owner code.
"""
import re
from .oneshot import SPEC_HASH
from .oneshot_archive import APPROVED,Refused

DISABLED='AUTHENTICATED_EXECUTION_DISABLED'


def require_live_reservation(reservation):
    """No real reservation capability can be issued or accepted in V2.6G."""
    raise Refused(DISABLED)


def approval_requirements(revision,source_hashes):
    """Review metadata only, never a grant or accepted reservation capability."""
    if (type(revision) is not str or not re.fullmatch('[0-9a-f]{40}',revision) or
        type(source_hashes) is not dict or not source_hashes or
        any(type(k) is not str or type(v) is not str or not re.fullmatch('[0-9a-f]{64}',v)
            for k,v in source_hashes.items())):
        raise Refused('REVIEW_METADATA_REQUIRED')
    return {'environment':'LIVE','spec_sha256':SPEC_HASH,'source_revision':revision,
            'source_hashes':dict(source_hashes),'archive_root':APPROVED,
            'attempts':1,'retries':0,'redirects':False,'pagination':False,'seconds':15,
            'requires_native_identity':True,'requires_unique_session':True,
            'authorises_execution':False}
