# V2.8C implementation

Local implementation only. Baseline main: `52568b3e2a69c36296f7b3fe2fc502b9c5a290eb`.
Source seal: `9a8b0960f0beefe7fb7fbd116cfa320bdfe6b18a2414c936b370a8c3c58445f2`.
Catalogue SHA-256 (LF-normalised): `2d5f5b38efb65a0cffd5f63ad38a7da62344d653bdba84dad9438cf1eac96bf9`.

The existing supervisor/worker entry, protected Archive, journal.json, Windows Job fencing, terminal provider, credential pipe, restricted HTTPS exchange, CandleTransport rate-delay helper and strict candle publisher are reused. bounded_acquisition.py adds the finite branch; bounded_history_entry.py is a thin terminal frontend. No new HTTP client, credential cache, archive or database is introduced.

One source/identity/rights-bound version-4 grant admits one parent namespace and one persistent worker. The terminal token is read once after durable overall reservation and sent once through the existing anonymous pipe. The worker must ask the parent to reserve each exact catalogue index, charges an immutable spent marker before dispatch, publishes raw/validated files and a manifest, and waits for parent verification before advancing. Never/reserved/attempted/completed/failed/unknown are distinct. Counts are budget reservations, including ambiguous pre-dispatch reservations; they do not imply every reserved request reached HTTP.

The 106 unchanged specifications cover [2024-09-01, 2025-09-01): 105 windows of 1,000 M5 slots and one of 120; 105,120 calendar slots. No count parameter, host/date override, skip, retry, redirect, pagination or fallback. The old catalogue's proposal IDs, destinations and source are reference-only, non-authorising planning metadata. Runtime artifacts are independently named raw/validated/manifests/v26c_year_NNN.json inside the one approved parent namespace; none of the 106 old proposals is activated.

Startup/reservation: 15 s. Hidden token input: 120 s. Each reservation through request/validation/publication/verification/cleanup: 15 s. Whole acquisition after token validation: 1,800 s, including waits and cleanup; no extension. One second is reserved for fencing. Token refusal has a separate one-second fencing allowance and cannot start acquisition. Rate spacing is at least one second after the preceding response completes, using the existing rate-delay helper.

Peak new-artifact bytes, including pending replacements and catalogue spent markers, are capped at 256 MiB. Ordinary publication leaves 1 MiB for accounting; journal/result publication can use the reserved portion. Free disk space is checked before execution and every publication. No deletion/fallback creates capacity.

The existing research importer recognises catalogue-bound per-window receipts and retains all original rights/hash/provenance/independence checks. Synthetic execution artifacts remain ineligible for real research provenance. No strategy evaluation or automatic dataset import occurs. Existing single-session/pilot behavior remains selected by its original entry path.
