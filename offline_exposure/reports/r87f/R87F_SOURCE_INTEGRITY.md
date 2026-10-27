# R.87F source integrity

All 451 monitored working-file hashes equal their R.87F before values through testing, commit and push. Only .github/workflows/ci.yml changed relative to the parent Git tree. Full records: source_before.json and source_after.json.

- forex_bot/bot_loop.py: `2f1c36dc025d114685e4424402f6866c66aa6eb37d28717027c502a4f447118d`
- forex_bot/exposure_view.py: `ab7b446d7b1491832e311eaf594e4ba70a9e349becef72df88197cbbf6625405`
- offline_exposure/fake_coordinator.py: `08ecf35832cea2196d115cf151c0f42b3ca92fa1807c2cdb88047622bda9b2df`
- offline_exposure/run_checks.py: `104bc60970b74a9a00dcba52b3715783d7b63b1dd7d358aec39c508c3f2ce04a`
- offline_exposure/test_contract.py: `6f1df8e850d3ea0b08ed771d40d1b7e9e29e52a6c318dc061135a9d54b0ce335`

The R.86 sealed reference remains a2310a7f2d2aee4b60c3c471cdd56ed48c72e2ed29232047c404209537e58d81. The current wrapper hash differs by design of the existing checkout; the mismatch is not resolved or newly accepted as an operational seal. No protected hash or existing test was changed.
