# Corrupt-state recovery

TESTED on synthetic files under the pytest temporary path.

Malformed JSON, truncated JSON, a non-object root, a non-integer schema version, an authorisation value other than BLOCKED or ALLOWED, a non-boolean `active`, and a missing `active` are classified invalid. The original bytes stay in place. Effective authorisation is BLOCKED. Known strategies are inactive. T12 through T18.

A missing path is the one case that creates a new document. That document is schema version 1, authorisation BLOCKED, and all six strategies inactive. T19.

A `PermissionError` from the text read, while the path exists, is classified unreadable. It does not create a replacement file. The reason is `safety_state_unreadable`. T20.

Recovery does not write ALLOWED over a bad file. T27.

`RecursionError` during `json.loads` is classified invalid in source. That path was not given its own fixture. UNVERIFIED as an executed case.
