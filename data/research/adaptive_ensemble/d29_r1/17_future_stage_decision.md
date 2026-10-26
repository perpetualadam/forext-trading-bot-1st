# FUTURE STAGE DECISION

Recommended next stage: controlled read-only registry response discovery.

Offline manifests do not show whether a layer-blob response is direct, challenged, or redirected. Another reconciliation pass cannot answer that. Full layer acquisition is not the next stage: the storage host is unauthorised and the four time limits are MISSING.

A discovery approval would need to name registry-1.docker.io and, only if a challenge appears, auth.docker.io. It would not name a storage host. A redirect stops the stage. No token is stored, no proxy is used, and no retry is allowed. The artifact identities are the unique compressed digests. Response bodies are capped at 1,048,576 bytes so a layer body is not retained. The request ceiling for discovery is one token plus the registry attempts in the state machine, with storage transitions removed.

The approval must also supply connection, inactivity, request, and stage deadlines. D.29-R1 does not choose those numbers. Discovery would produce response observations, not verified layer bytes, ABI evidence, or libc evidence. It would not authorise extraction or execution.

This recommendation was not executed.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
