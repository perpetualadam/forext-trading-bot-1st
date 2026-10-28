# Confirmation failure review

Reviewed 2026-10-28 against published baseline 223896fea7d18a7cf73e55180be450223ed38134 and the separately retained local activation implementation.

The terminal reads one line. Two concatenated copies are therefore one malformed response, correctly rejected by exact equality. The missing usability feedback is now corrected: the expected phrase is displayed clearly; mismatch explains exact-once entry and no retry; acceptance is announced before subsequent admission checks. No trimming, splitting, repair or automatic retry occurs. Rejected input is not echoed.

Read-only native archive inspection found no grant, journal, grant claim, worker claim, pending publication or response batch. The pre-fix source seal matched 675b0a6dda187beaa62851c4124999d1a0ee9b33b0028770359311d249e50a7d. The refusal precedes creation of the in-memory confirmation proof, durable grant, worker and credential/network calls. Together these establish that this failed invocation created and consumed no authorisation, started no worker, retrieved no token and dispatched no authenticated HTTP request. Absence of a token prompt alone was not used as evidence.

Request ID 5ff42331dd944740bf82acb1e326b82b was unused. Its source-bound preparation is stale after this UI correction and must not be reused with the changed sources. Original preparation and seal are preserved locally as *.before_confirmation_fix.json. No permit, journal or consumed marker was removed or overwritten. A fresh, non-authorising proposal is documented in NEXT_REQUEST_INSTRUCTIONS.md and requires separate approval.

Publication is restricted to the pure confirmation helper, its integration into the published disabled frontend, UI tests and these three reports. The published unconditional admission refusal is unchanged. Existing local activation implementation and its seal/preparation are excluded. Operational trading sources, R.56 source gate and permit/consumed metadata are unchanged. Existing scheduler modifications and local research data are preserved; scheduler remains enabled with successful runs. Production trading remains NO-GO.
