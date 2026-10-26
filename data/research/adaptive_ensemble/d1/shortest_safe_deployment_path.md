# Shortest safe deployment path

No phase below is authorised. A shorter path that restarts the current container, builds from the repository root, or skips the lock and the rollback drill is not safe. It would leave the five differing runtime files undeployed, or it would deploy them without a recovery test. The weekend does not remove a phase.

## Phase 1 — source readiness

Confirm the allowlist still matches the tree. Change `live_safety.py` so a startup cannot drop unknown strategy-row keys or replace an unknown schema with a blank document. Change the strategy default so a strategy is inactive until the durable file is accepted. Review the lifespan and list every broker and database call. Do this on copies and synthetic files.

Pass: the new writer preserves unknown keys and refuses to overwrite an unknown version. Fail closed: any test that uses `data/ops` or the live database.

## Phase 2 — offline tests

Under a separate approval, run the existing unit tests and new safety tests with broker clients mocked and with a disposable database. Do not start the real scheduler against OANDA.

Pass: the approved set is green on this tree, and a test fails if a real broker host is opened. Fail closed: any live credential use.

## Phase 3 — reproducible build

Resolve the G.14 receiver and lock blockers under their own approvals. Pin direct and transitive wheels for the recorded target. Build once in an isolated context that is not the repository root and does not contain the two backup files.

Pass: the image manifest lists the staged files and the locked wheels. Fail closed: a build that still runs `pip install` against the network, or a context that is the repo root.

## Phase 4 — candidate verification

Inspect the candidate without promoting it. Check entrypoint, safety gate, DDL on a fixture, and shadow writes on a fixture. Confirm no live broker call.

Pass: bytes and behavior match the approved manifest. Fail closed: any difference, or any real account call.

## Phase 5 — rollback

Prepare a recovery that does not use image `sha256:a19a2208fcf30f8fa1cf61442cf021dec6d99d809b6907836c834922bfe3e2a5`. Test it on a copy of the safety document and a database fixture. Show that a failed start does not destroy a newer safety schema.

Pass: the drill restores the previous behavior and the copied state. Fail closed: untested rollback.

## Phase 6 — deployment decision

Re-read every blocker. Obtain a separate production approval. Keep live-order authorisation BLOCKED unless a different approval says otherwise. Deploy with a written stop condition. Verify the new container identity before leaving it running.

This stage does not approve Phase 1 edits, tests, downloads, Docker, or deployment.

The first offline remediation that is safe to propose, and still needs its own approval, is the safety-state writer fix and its synthetic tests. That fix does not make the bot deployable.
