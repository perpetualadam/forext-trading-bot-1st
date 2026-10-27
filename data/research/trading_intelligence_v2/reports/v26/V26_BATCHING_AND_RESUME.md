# V2.6 Batching And Resume

Plan is immutable, M5 aligned, <=3*366 days, <=5000 intervals/window,
<=20,000 windows total. Pagination advances fixed requested windows, never the
last returned candle, so empty replies cannot create infinite loops or masquerade
as coverage. Cancellation is checked before requests, while pacing/backoff and
between batches. A request already in progress is bounded by socket/deadline
behaviour, not instantly cancellable. Progress callbacks contain safe counts.

OS nonblocking writer locks serialize archive publication; closing releases the
lock, including OS process cleanup. Windows uses msvcrt, POSIX flock. No PID-file
stale-owner guessing. Tests cover lock exclusion and interruption; cross-host
filesystems, power loss and hard process-kill durability were not tested.

Raw envelope atomically stores original response bytes as base64, original
retrieval time and public request range. Normalized rows retain decimal lexemes.
Commit record is published LAST with hashes of both artifacts. Resume verifies
hashes, schema, range, retrieval evidence and canonical rows. Durable orphan raw
can finish without refetching. Partial/ambiguous staging stops for review; nothing
is deleted or trusted as complete. Different committed content cannot overwrite
immutable batches. Progress is a rebuildable index, not completeness authority.
fsync plus replace is used; POSIX also syncs the parent directory. Windows and
network/cloud filesystem power-loss semantics remain a deployment review item.

Production remains NO-GO.
