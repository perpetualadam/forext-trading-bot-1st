# Refreshed V2.8D66 verification

Windows: 352 passed, zero failures/errors/skips (all original 346 plus six new header regressions). Linux: 140 passed (all original 134 plus six), zero failures/errors/skips.

- Windows full, headers-final-native-bounded.txt: 48 passed; log SHA-256 44eedeeb56e0db0a293b4ed35a5cfaaf59447100869ce00940151e70845389be.
- Windows full, headers-final-native-remaining.txt: 55 passed; log SHA-256 f76d7fb8a1c3abfceafa161c5f31936d055a770d7cd590a0a106a2276f46d84f.
- Windows full, headers-final-native-diagnostics.txt: 25 passed; log SHA-256 aba17a65b76dab16d6e221cdff5aceb08c3f4c31f65606b4f533adfa5f0e1ebf.
- Windows full, headers-final-native-security.txt: 67 passed; log SHA-256 009ff2e013d73984a3f6514a9df522d0f387fe1b8cb5e749dc7319d6d57af47f.
- Windows full, headers-final-native-rollover.txt: 46 passed; log SHA-256 cfd15ef2c41f1892ec0400853d2407280fe5fd70e7050693f2ee6cf37e9550e6.
- Windows full, headers-final-native-scope.txt: 12 passed; log SHA-256 a2ea74a0ba73a233110781f4f697e0aeb72d632336de43aa77a04f07db4c2547.
- Windows full, headers-final-native-v28d_research_run.py.txt: 21 passed; log SHA-256 d4e9c79db6d20852350219b3f4f5f0ad77d05aefdd23621fdcb516d018f3e48c.
- Windows full, headers-final-native-v28_run.py.txt: 24 passed; log SHA-256 d19a202346f2bf16fe15b7a0ef25419d93629effbe65a685fb6b24cdaf18c9e2.
- Windows full, headers-final-native-v28a_run.py.txt: 24 passed; log SHA-256 534146aa9c2ad0a7f0cde6c5f2b81bc5aa04c1eba904974735309f5aac23b283.
- Windows full, headers-final-native-v28b_run.py.txt: 30 passed; log SHA-256 585025ac06cbbfc75ff8b110062d0e32762929072d32cce689d3146ad3abc81c.
- Windows repetitions, headers-final-native-isolated-1.txt: 1 passed; log SHA-256 3951323af289fbcbad987d53de04bbd829e8e753ad6db48dfef5a5a4e3d02af2.
- Windows repetitions, headers-final-native-isolated-2.txt: 1 passed; log SHA-256 fdb0bf35bd2c043a77f05d639b3a1a4a2266a3f86cbc6d47e581960b71b10617.
- Windows repetitions, headers-final-native-isolated-3.txt: 1 passed; log SHA-256 0b15b202feaa71185ae01400d437ba0017ccb82771fe519bc1963e732c8066dd.
- Windows repetitions, headers-final-native-isolated-4.txt: 1 passed; log SHA-256 3e12aabde84352731c23f058a39412790706d4f7400cad58ec78c29a492b1648.
- Windows repetitions, headers-final-native-isolated-5.txt: 1 passed; log SHA-256 9b7e6443558a2e179733b089c18935cb6804f0deae293de40380ef38879e15ca.
- Windows repetitions, headers-final-native-order-1.txt: 5 passed; log SHA-256 fa8982d7a0048028cd6054ebc69dd8b48f3550e54d65ebb3c7b02238ee7ed827.
- Windows repetitions, headers-final-native-order-2.txt: 5 passed; log SHA-256 ac3297790428d2df7b1591509d77c76f540fc98e89f99d87ce8e3dba540a808e.
- Windows repetitions, headers-final-native-order-3.txt: 5 passed; log SHA-256 d84a3210587af001c6ec32fe4f8dec5486b60d8d16c33952487b51a32060daeb.
- Linux full, bounded.txt: 48 passed; log SHA-256 631328abe2837de04761692f3d5f2625e393529dd3203e8452a075bfa825ff3c.
- Linux full, remaining.txt: 55 passed; log SHA-256 a398f1ccc5b8b8dfc294a083df011d209e852eac17dd4e5fd83b691e00615677.
- Linux full, diagnostics.txt: 25 passed; log SHA-256 d6a1c2ba45cddfce0990ce91de9c79af8a636ee4bf0676ca8bd4a4074a96e4f7.
- Linux full, scope.txt: 12 passed; log SHA-256 2d1c8bc6d158d7a1c5238f425e8bfa8eb35fe34e4a513c38862429591bf93cf4.
- Linux repetitions, headers-isolated-1.txt: 1 passed; log SHA-256 6df2cfd099acadb98e15e79e03aee87953a1714c679cba1dfa039fd4866596ed.
- Linux repetitions, headers-isolated-2.txt: 1 passed; log SHA-256 1202500b2bda3aec50f2f4fe50a3deb5cb3ec43c016da4daf87d51a4b68329aa.
- Linux repetitions, headers-isolated-3.txt: 1 passed; log SHA-256 200f50058e2b853b30894f1b3c743dcde6bd07074956ef5fb8623068b8888fda.
- Linux repetitions, headers-isolated-4.txt: 1 passed; log SHA-256 b3f693b6a95dc3fcd9ba89bb18eaa3b33b35f6c06576325706b43d79e8ba44c1.
- Linux repetitions, headers-isolated-5.txt: 1 passed; log SHA-256 61c391fd8d2880be8ee9465481572d6eb361076c76dc6644957afa565a19d838.
- Linux repetitions, headers-order-1.txt: 5 passed; log SHA-256 51a0b811c5526365cf0ed80c97a9b38232d6b04e4ae916405b9bdc63c319f571.
- Linux repetitions, headers-order-2.txt: 5 passed; log SHA-256 191a4632f0a0a7fc395650444abea75dabef8b944b387f89eb4810d364ce8429.
- Linux repetitions, headers-order-3.txt: 5 passed; log SHA-256 f1d85c4222da419bb74a2bb35803c0afcc74a0f56dd2b60d2d47c2ef47b7b527.

Each platform ran five isolated targets and three original five-test prefixes (eight delayed-header repetitions, 20 executed tests). Full suite results are separate. Linux used a verified source-only native-filesystem copy; no real data or credentials were copied.

Production seal 6ea343adb926647424dfffd8ecf77679b9d442b7e4391c2aff7c539580cc6525; catalogue b663097a02d007a6ff055946ae1c602fe9e16c33b3f9284e17a3b5ac187dc768. Original slow-token assertions and delayed-header timeout/stage assertions retained. No production/CI bytes changed in this correction; six test/fixture paths changed.

Partial records SHA-256 81b006a153237ac42dabbbd817a5e56b80493cb82b89bd0db4705a207a64a8a9; dataset file SHA-256 007d85b7c95176a830ddeddf799c58f29401960773c924754f25a2a1bc174ab0; manifest SHA-256 54782a07b77b340180f1dd6bf37ac8c1a99a6f06ee94a3ebd05ec9ea37bb2c12. Independent-process reopening and prior protected evidence checks passed.

No authenticated requests, executable LIVE grants, replay, staging, commit or push. Production NO-GO.
