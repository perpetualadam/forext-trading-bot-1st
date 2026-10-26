# R.86 Ambiguous Close Reporting

Evidence: executed `test_34`. The close state is `CLOSE_RECONCILIATION_REQUIRED` with null confirmed and remaining units.

The report category is `UNRESOLVED_EXPOSURE`. Units and confirmed-closed units are null. A parsed body showing 600 does not become the confirmed quantity. An empty body does not become a full close. The permit is not an input the report can reset. `broker_requests` is 0.

The same null-unit unresolved line applies for a wrong trade, a missing target, an incomplete body, and a failed retrieval: the snapshot is not used to fill confirmed units. The operational cycle test kept `network_permit` at its prior value after an incomplete startup view.

No close retry is implemented in the report.
