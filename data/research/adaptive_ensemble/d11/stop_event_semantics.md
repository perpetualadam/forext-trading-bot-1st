# D.11 stop-event semantics

The event is created at import. Start clears it only after it has decided that no live worker exists. Stop sets it under `_poller_lock` and never clears it. One generation uses that event. A new start does not clear it while the old worker is alive.

The poll loop checks the event before each `getUpdates`. After a response, `process_updates` advances offsets but skips `process_update` for every item once the event is set. `process_update` also returns immediately when the event is set. The poller then breaks.

Updates that arrive after shutdown is requested are acknowledged for offset purposes and are not dispatched. Updates are not discarded while the service is running normally.

`reset_telegram_control_for_tests` calls stop and, if the worker is still alive, returns without clearing the event.
