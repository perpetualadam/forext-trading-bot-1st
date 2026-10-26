# Remaining risks

1. The inactive-strategy return in `bot_loop.py` was not executed. Default strategy flags were checked. That is not proof the loop returned before sizing.

2. The PostgreSQL statements were not executed. Restart protection was tested by feeding a synthetic unresolved row into the same decision function the reader uses. A later offline test database would still be required before anyone treats the SQL as proven. Production was not migrated.

3. `orders.py` still stores an unknown status as `PENDING` in memory. The new gate blocks on the database status and the process map before a new client id. `orders.py` was outside this stage's edit list.

4. With order persistence switched off, every new broker entry is refused because recovery is unreadable. The default is persistence on. This stage did not change that default.

5. The trading loop's exception handlers were not entered. The functions those handlers call were tested directly.

6. No broker, practice, or live order was sent. Nothing here is evidence of profit or of a working broker connection.
