# SQL synthetic tests

A fake cursor recorded the SQL string passed to `execute`. That cursor did not parse or run the statement. These results are not PostgreSQL engine results.

| Check | Result |
| --- | --- |
| Captured SQL includes PENDING, PARTIAL, UNRESOLVED | Yes |
| Captured SQL includes FILLED eligibility other than exact CONFIRMED_FLAT | Yes |
| Missing, NULL, and empty metadata | Kept by the Python predicate. Not flat |
| Malformed metadata and unknown marker | Fail closed at ingest |
| CONFIRMED_FLAT | Excluded by itself. Does not override UNRESOLVED |
| Query exception | Fail closed |
| Empty result | Distinct from failure |
| Parameters | Fetch SQL has no `%s` and the captured parameter tuple is None |
| Schema change | None in the selection text |
| PostgreSQL connection | Not opened |

Actual PostgreSQL semantics: NOT_EVALUATED.
