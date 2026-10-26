# RESPONSE-DRIVEN REQUEST FLOW

This is a specification. It is not a client and it was not executed.

D.29 listed one anonymous registry GET, one token GET, eight authenticated registry GETs, and eight storage GETs. That list is a possible ceiling, not a sequence the registry must follow.

A later response may be a direct blob, an authentication challenge, a redirect, or an error. Behaviour may differ between digests. Storage hosts are not authorised. No request is asserted to require a storage GET, and one token GET is not asserted to be sufficient.

States:

1. Select the next unique digest that has not been attempted.
2. Send one registry GET for that digest, only to a host named by a future approval.
3. If the response is a challenge, allow at most one token request for the whole stage. A second challenge stops the stage. Do not claim the token will work for later digests.
4. After that single token, one continuation registry GET is allowed for the digest that was challenged.
5. If the response is a redirect, do not follow it. If the target host was not named by the future approval, stop. Record only a sanitised redirect event.
6. If the response is a blob body, stream it under that digest's declared size cap and verify the size and SHA-256 before promotion.
7. A storage GET exists in the ceiling only when a future approval names the storage host. This specification does not name one.
8. Any error, unexpected scheme, unexpected port, or extra redirect hop stops the stage. There are no retries and no automatic resume.

The proposed ceiling is 18 GET responses: one token, one extra registry continuation, one registry attempt per unique digest, and one storage attempt per unique digest. With 8 unique digests, unused branches stay inside the ceiling. The ceiling status is PROPOSED_NOT_AUTHORISED.
