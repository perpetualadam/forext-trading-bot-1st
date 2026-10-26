# Stage D.6 resource-ownership invariants

| Invariant | Result |
| --- | --- |
| A. No real broker, database, scheduler, trading loop, Telegram service, or order router | Holds. Fakes and denials recorded zero network calls and zero order-route calls. |
| B. Created resources are accounted for | Holds. Every fake connection and task is in the case report. |
| C. A fatal failure leaves no unreported running fake task | The application left tasks running. They were reported, then the harness cancelled them. |
| D. Fatal failure closes resources the implementation promises to close | The implementation's task `finally` does not run for pre-yield failures, so the promise is not reached. Observed defect. |
| E. Anything left open is a defect or an ownership exception | Connection drop without close, pre-yield task leaks, and shutdown leaks are defects. The success-path retained connection is ownership exception D6-OWN-01. |
| F. Authorisation stays BLOCKED | Holds in every case. |
| G. Six strategies stay inactive | Holds in every case. |
| H. No injection grants authorisation | Holds. |
| I. No injection calls real order routing | Holds. Wrappers were not called. |
| J. Repeated failure does not corrupt the synthetic safety file | Holds. File authorisation stayed BLOCKED. |
| K. Nonfatal errors stay distinct from fatal errors | Holds. Account summary, reconciliation, and database-unavailable continue. Broker construction and pre-yield task failures escape. |
| L. Harness cleanup is not counted as application cleanup | Holds. Pending tasks and `close_calls` are recorded before the harness cancels or closes. |
| M. Failed application cleanup is visible | Holds. `harness_cancelled` and `harness_closed_connections` are non-zero exactly where the application did not finish cleanup. |
| N. A pass is not merely "an exception occurred" | Holds. Each case records yield, pending tasks, close calls, and whether the global connection is still held. |
