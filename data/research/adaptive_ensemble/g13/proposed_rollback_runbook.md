# Proposed rollback runbook

This document is a plan. It was not executed. It does not authorise a Docker build, a deployment, a restart, a database restore, a broker call, or a rollback.

The current condition is that no verified rollback image exists. The no-go decision below applies until that changes through a separate approval.

## Current facts

- Running container: `forexttradingbot1st-bot-1`
- Container ID: `5fcbcff7173eee98f6228b901fab96fd24474038852ef1f4cc3fbccd138edd32`
- Running image: `sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25`
- Running-image classification: `ROLLBACK_CANDIDATE_PARTIALLY_VERIFIED`
- That image is not a verified safe rollback target. It has the Stage A fail-closed startup control and the new-order authorisation gate. It does not contain the later market-provenance protection, the missing-candle position-management repair, or the later protective-close direction and size guard.
- Excluded historical image: `sha256:a19a2208fcf30f8fa1cf61442cf021dec6d99d809b6907836c834922bfe3e2a5`
- Do not restore or deploy the excluded image.
- Effective live-order authorisation observed at the G.13 baseline: `BLOCKED`
- Durable reason observed at that baseline: `operator_preflight_blocked`
- Six original strategies were inactive at that baseline. `BLOCKED` is not itself proof that every stored strategy flag is inactive.
- Live database compatibility: `LIVE_DATABASE_COMPATIBILITY_UNVERIFIED`
- Docker build-context behaviour: `DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED`

A rollback is not only an image change. The process also depends on the live OANDA account, the PostgreSQL volume, the durable authorisation file, strategy flags, broker-side orders and positions, and the mounted operational and research directories. A stale database or a stale safety-state file is not an authoritative description of broker positions. Do not restore a database snapshot over newer live trading records without a separately approved reconciliation design. Do not assume a broker-side protective order can be recreated without observing the actual broker state.

## A. Aborting a proposed deployment

If no replacement container has started and no persistent file or database has been changed, leave the existing running system unchanged. Do not restart it in order to "confirm" that it is still the old system.

## B. Recovering from a failed deployment

If a future deployment has changed persistent state, starting an older image does not undo those changes. Stop and use sections C and D. Image replacement alone is not recovery.

## C. Rolling back after database or state changes

Treat database rows, the safety-state document, shadow files, and broker positions as separate recovery problems. Restoring an older image after any of those have changed requires evidence that the older code can read the newer state without widening authorisation or inventing positions. That evidence does not exist for the live database.

## D. Recovery when no verified rollback image exists

This is the current condition. The no-go decision is mandatory.

No-go: do not deploy a candidate, do not restart the running container, and do not switch images. The partially verified running image is the process already in production. It is not a second known-good image that can be rolled forward or back to. The excluded historical image stays excluded.

## Checkpoints

Each unknown item is `UNRESOLVED_OPERATOR_DECISION`. None of these checkpoints was performed.

1. Pre-deployment image identity verification. Required before any future deployment. Not done. `UNRESOLVED_OPERATOR_DECISION` for who compares the image ID.
2. Immutable candidate image reference. No candidate image exists. A future reference must be a digest, not a movable tag. `UNRESOLVED_OPERATOR_DECISION`.
3. Verified rollback image reference. Unavailable. Classification remains `NO_VERIFIED_ROLLBACK_TARGET`.
4. Evidence of compatibility with the live database schema. Not established. Classification remains `LIVE_DATABASE_COMPATIBILITY_UNVERIFIED`.
5. Safety-state compatibility evidence. Static source review only. The live file was not rewritten. A newer schema that this parser rejects would be overwritten with a blank blocked document on startup.
6. Mount compatibility evidence. Static source review only. The operational mount and the shadow mount were not read or modified for this plan.
7. Explicit operator authorisation. Absent. `UNRESOLVED_OPERATOR_DECISION`.
8. Maintenance window. `UNRESOLVED_OPERATOR_DECISION`.
9. Pre-change backup requirements. A future change that can alter PostgreSQL, `/app/data/ops`, or broker-visible state needs a backup design approved separately. No backup location is named here. `UNRESOLVED_OPERATOR_DECISION`.
10. Backup integrity verification. `UNRESOLVED_OPERATOR_DECISION`.
11. Recovery point objective. `UNRESOLVED_OPERATOR_DECISION`.
12. Recovery time objective. `UNRESOLVED_OPERATOR_DECISION`.
13. Fail-closed startup verification. Required after any future process start. The current source forces effective authorisation to `BLOCKED` on startup. This was not re-tested against the live file.
14. Strategy inactivity verification. Required after any future start. Stored strategy flags are a separate control from the effective order gate.
15. No-new-order verification. Required after any future start. Close actions are not gated by the new-exposure check, so "no new order" must be observed at the broker, not inferred only from `BLOCKED`.
16. Broker reconciliation requirements. Required before trusting local rows after any failed deployment or rollback. Local state must be compared with the live account. No broker call was made for this plan. `UNRESOLVED_OPERATOR_DECISION` for who performs it and how differences are resolved.
17. Post-deployment health checks. `UNRESOLVED_OPERATOR_DECISION`.
18. Rollback triggers. A future trigger list must include failed startup, unexpected effective authorisation, a strategy becoming active, any new broker exposure, schema startup failure, and safety-state persist failure. The trigger authority is `UNRESOLVED_OPERATOR_DECISION`.
19. Rollback decision authority. `UNRESOLVED_OPERATOR_DECISION`.
20. Incident logging. `UNRESOLVED_OPERATOR_DECISION` for the log location and the person who writes it.
21. Recovery validation. Must include image identity, effective authorisation `BLOCKED`, six strategies inactive, no new broker exposure, and broker reconciliation. The acceptance criteria beyond that list are `UNRESOLVED_OPERATOR_DECISION`.

## Decision

No verified rollback target is available. The decision is no-go for deployment and no-go for rollback.
