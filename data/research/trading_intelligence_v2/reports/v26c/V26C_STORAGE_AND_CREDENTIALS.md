# Storage and credentials

Native root is exactly `C:\TradingResearchData\OANDA`, outside this repository
and OneDrive. There is no fallback or configurable native root.
`prepare_native_binding()` explicitly created only local directory-identity
metadata. It did not create a session, permission grant or live authorisation.
Acquisition-side binding refuses a missing pin rather than creating one.

The adapter checks fixed local NTFS, owner SID and owner+SYSTEM full-control
ACLs, existing directory identities, ancestors/reparse points, traversal,
reserved device names and hardlinks. It retains no-delete-share directory
handles with FILE_LIST_DIRECTORY access. A metadata-only handle proved
insufficient in the first native test; the test directory was restored, access
was strengthened, and the real directory-replacement refusal subsequently passed.
ACLs were not relaxed; administrator/SYSTEM/owner override is not prevented.

`oneshot_response.publish_candles()` binds the existing strict V2.6 validator to
native raw/validated/manifests directories, verifies hashes and publishes the
manifest last. Invalid/extra-key responses refuse before raw publication.
Files are exclusively staged, flushed and atomically committed. Immutable
publication is no-clobber even during a race; mutable journals alone explicitly
replace. Interrupted pending files require review, not automatic repair.
Storage firmware and malicious owner rollback are outside the guarantee.

Portable tests write only ignored `outputs/v26c/fixtures`. Native session tests
write only `research_outputs/v26c_synthetic_sessions`; they require the approved
root's real pin/ACL checks, label every grant synthetic, and cannot enable HTTP.
Native synthetic candle batches are also retained externally. No identity pin,
SID, local session journal, archive content, token or account identifier enters Git.

Synthetic secrets travel only through anonymous pipes after durable reservation.
They are absent from argv, environment, request URLs, outputs, manifests and
exceptions. Worker stderr is discarded; errors contain fixed codes/type names,
not bodies or exception messages. Synthetic persistence scans pass. No real
token, `.env`, credential manager or production credential store was accessed.
Python immutable strings are not promised secure memory zeroisation.

The [official authentication documentation](https://developer.oanda.com/rest-live-v20/authentication/)
describes bearer personal tokens with broad sub-account access. Application
GET-only restrictions are not broker-issued read-only token scoping. A future
credential bridge and authenticated worker require separate review; neither is
enabled by these synthetic tests.
