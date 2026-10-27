# R.87D offline patch review

Reviewed actual source, immutable pure model, runner barriers, and tests. All four raw file hashes match the requested expected hashes. Source imports were inspected through AST without executing application modules. Only the offline runner references the new pure module by filename; operational code has no import/caller added.

The coordinator serializes state transitions under one RLock. Active/latest generation publication and single-use completion are enforced. Malformed request tokens are refused without mutation; invalid current completion fails and consumes completion; managed revision cannot roll back. Superseded responses cannot overwrite or advance revision. Duplicate dispatch is refused, frozen intents cannot dispatch, release_unsent cannot remove dispatched intents, and transfer_fill retains occupied slots and unrelated intents. Reservation counts occupied/pending slot union. Synthetic publication trusts supplied complete evidence; this is not broker authentication, crash safety, process safety, durable idempotency or exhaustive verification of arbitrary inputs.

Separately reviewed prerequisite: forex_bot/exposure_view.py is a new untracked standalone pure module, not a modification of operational callers. It has only dataclasses/math imports, no I/O, no management API and fail-closed default policy. Its exact supplied hash and previous reviewed lifecycle/numeric corrections are retained. It rejects occupied-slot OPEN and unknown/unresolved pending exposure. Both required discovery cases remain count 1 without management authority. No production integration exists.

A three-file-only commit would be incomplete: run_checks.py loads forex_bot/exposure_view.py, which is absent from current main. Therefore the independently reviewed prerequisite must accompany the three-file coordinator patch. This is the explicit conditional model inclusion permitted by Phase F, not an unreviewed operational integration. Reports, logs and research artifacts are not part of the proposed commit.

- `offline_exposure/fake_coordinator.py`: `08ecf35832cea2196d115cf151c0f42b3ca92fa1807c2cdb88047622bda9b2df`
- `offline_exposure/test_contract.py`: `6f1df8e850d3ea0b08ed771d40d1b7e9e29e52a6c318dc061135a9d54b0ce335`
- `offline_exposure/run_checks.py`: `104bc60970b74a9a00dcba52b3715783d7b63b1dd7d358aec39c508c3f2ce04a`
- `forex_bot/exposure_view.py`: `ab7b446d7b1491832e311eaf594e4ba70a9e349becef72df88197cbbf6625405`
