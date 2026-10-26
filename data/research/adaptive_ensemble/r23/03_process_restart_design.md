# Process-restart design

The parent test launches `tests/r23_process_driver.py` with the Python interpreter, `-B`, and explicit arguments. It does not use a shell. Process A creates one synthetic order. The parent waits for that process to exit. Process B is a new interpreter and starts only after that wait returns.

Each child installs the socket, DNS, and dotenv barriers before importing `forex_bot`. It clears `EXEC_ORDER_OFFLINE_STORE`, sets persistence off, points the synthetic safety file at `r23`, and arms the store path passed on the command line. The path is under `r23`.

Process A runs `evaluate` with the deterministic offline selector, the AI vote, the RL veto, sizing, and risk. The inert adapter is called once. FILLED or UNRESOLVED is written through the existing order-state functions into the JSON store.

Process B calls `initialise_application` with the offline startup ports. The provider returns `read_offline_exec_orders()`. The startup branch then calls `select_rows_for_recovery` and `ingest_recovery_snapshot`. Process B runs `evaluate` again. Exposure is already held, so the iteration blocks before reservation. The inert adapter is not called.

No in-memory map is passed between the processes. `run_bot` and the production lifespan are not called.
