# R.87D operational baseline comparison

Raw bytes were SHA-256 hashed with no line-ending normalization. R.86 source archive used: data/research/adaptive_ensemble/r86/R86_SOURCE_REVIEW.zip. Exact records also appear in operational_hashes.json.

- `forex_bot/bot_loop.py`: current `2f1c36dc025d114685e4424402f6866c66aa6eb37d28717027c502a4f447118d`; R.86 `a2310a7f2d2aee4b60c3c471cdd56ed48c72e2ed29232047c404209537e58d81`; MISMATCH
- `forex_bot/profit_protection.py`: current `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f`; R.86 `d57dfce057eb8e5bd318fd6a1bb4f36a979c45e6d4cd664a51fdbc6a7f09b51f`; MATCH
- `forex_bot/positions.py`: current `afd62ac98c593ee8d75871c12b421d489061b84113724923cdb6f4950edfe36a`; R.86 `afd62ac98c593ee8d75871c12b421d489061b84113724923cdb6f4950edfe36a`; MATCH
- `forex_bot/reconciliation.py`: current `852a6e2a4da35bce50e68f82cd2e625f25bf36a707a3ad258c3c9d09011a9dbd`; R.86 `852a6e2a4da35bce50e68f82cd2e625f25bf36a707a3ad258c3c9d09011a9dbd`; MATCH
- `forex_bot/entry_journal.py`: current `961b3e167bbc8553a0febc2f8ace430e536ffce8389c1ab0a49227feaeb02dcd`; R.86 `961b3e167bbc8553a0febc2f8ace430e536ffce8389c1ab0a49227feaeb02dcd`; MATCH
- `forex_bot/close_journal.py`: current `b5dafd6f7d04e50ef2c4ee993d08733f8d60a73a31f3dbfd7844ab60c2a35483`; R.86 `b5dafd6f7d04e50ef2c4ee993d08733f8d60a73a31f3dbfd7844ab60c2a35483`; MATCH
- `forex_bot/startup_recovery.py`: current `69779649d606f6e6b0d3ac29bb2af6c536b2cee520e363b2c251726860c48658`; R.86 `69779649d606f6e6b0d3ac29bb2af6c536b2cee520e363b2c251726860c48658`; MATCH
- `forex_bot/position_recovery.py`: current `decab95661526606038856ad1a99b71c54897473bd7120cfa384a8d01db910a3`; R.86 `decab95661526606038856ad1a99b71c54897473bd7120cfa384a8d01db910a3`; MATCH
- `forex_bot/broker_close_evidence.py`: current `2f01fed308a3bf2f111b2bfad8a8610d45ec6bac92264c46877f08d7efd73bc8`; R.86 `2f01fed308a3bf2f111b2bfad8a8610d45ec6bac92264c46877f08d7efd73bc8`; MATCH
- `forex_bot/exposure_report.py`: current `6ecba78ed1c77af0cd72f00b37f58e1b7b876a33d612a0f08d995de235782290`; R.86 `6ecba78ed1c77af0cd72f00b37f58e1b7b876a33d612a0f08d995de235782290`; MATCH

Nine of ten required files match. bot_loop differs only at the wrapper/import boundary in a UTF-8-decoded source comparison (wrapper_boundary.diff); exact hashes above were computed from bytes. An initial diff display used the host default encoding and produced spurious glyph differences; that artifact was regenerated with explicit UTF-8. No operational file was written.

The local wrapper is intentional in the committed test seam, introduced before 529277b. Restoring the exact sealed archive would remove that interface and break six test consumers. Production hash acceptance remains unresolved; the offline patch does not claim a seal pass or grant trading readiness. No restoration or operational edit performed.
