# D.9 release interaction

`release_connection_after_failed_startup` was not modified.

It still clears `_pg_conn` and `_pg_cursor` only when they still point at the objects captured under `_pg_lock`, then closes those objects outside the lock. A second call finds null globals, creates nothing, and records no close error. The post-fix release schedule observed `borrowed_closed` true, empty second notes, and `release_created_connection` false.

Because close happens outside the lock, a new `get_connection` can publish a replacement while the old object is closing. The replacement schedule observed old id 1 closed and new id 2 published and open. The release did not clear id 2.

Initialization now holds the lock, so release cannot clear globals in the middle of an initialization. It waits, then sees the published pair. That is the safe overlap. The old D.8 schedule that released before publication, by racing inside connect, is no longer reachable without breaking the lock. The corrected test holds the first caller inside connect and shows the second caller cannot enter connect.

A failed initialization does not clear an already published object. The healthy-global schedule marked the published connection closed so a new attempt was required, then failed that attempt. `_pg_conn` still pointed at the original object.
