# Deadline and crash evidence

One monotonic start is taken at the HTTPS bridge entry, before imports/validation,
and carried into the existing supervisor. Total session budget is at most 15 s.
Up to 1 s is reserved inside it for cleanup; 3 s sessions exercise real TLS,
header and body stalls. The absolute work deadline crosses IPC into the worker;
it is never restarted for connection, headers, body, validation or persistence.
The parent's process fence remains the outer bound on blocking child operations.

Windows Job Object kill-on-close is attached before startup data/credentials;
POSIX starts a separate process group. Completion also fences the worker. All
tested timeout outcomes confirm worker exit within the requested total budget.
Server fixture startup/shutdown has separate bounded waits and joins; the server
thread is checked stopped after each session. No random sleeps are used.

The existing same-filesystem OS lock covers reservation through completion.
Immutable claimed-grant evidence precedes REQUEST_RESERVED; REQUEST_ATTEMPTED
precedes dispatch. A two-process real-HTTPS race makes exactly one request.
Every known error, timeout and success is followed by a restart refusal test.

All seven existing crash points are exercised through the HTTPS call path:
before reservation publication, after it, before dispatch, during dispatch,
after response, during raw publication and during final journal persistence.
The last two kill after pending-file flush before atomic rename. Claimed grants
and partial journals remain consumed; neither is recreated/reset. Pre-dispatch crash
points make zero HTTP requests; post-response points make exactly one. The
dispatch fault occurs after real HTTP bytes enter TLS, so server receipt may be
zero or one. A separate post-send stall proves fencing during transmission.
Ambiguous receipt is never probed by retry.

No claim of universal hard real-time execution, hardware power-loss durability,
malicious owner rollback resistance, remote non-receipt, broker-side cancellation
or exactly-once delivery. FENCING_UNCONFIRMED/DEADLINE_OVERRUN fail closed. The
parent avoids blocking buffered-pipe cleanup if process fencing is uncertain.
