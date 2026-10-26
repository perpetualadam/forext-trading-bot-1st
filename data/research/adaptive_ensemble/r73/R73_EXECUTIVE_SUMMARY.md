# R.73 Executive Summary

Classification: `R73_IMPLEMENTATION_PARTIALLY_VALIDATED`

`RESTART_DURABLE_IDEMPOTENCY_NOT_IMPLEMENTED`

`BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`

A live close now has a process-local operation. The bot submits the existing OANDA position-close helper only after it reserves that operation. It deletes the local live row only after a retrieved `ORDER_FILL` transaction shows the requested trade reduced by the requested units. A timeout, a missing transaction body, a partial fill, and a flat broker snapshot leave the row in place and block another live submission.

Paper, simulated, window-paper, and synthetic closes still use the previous local path.

The reservation is memory inside one process. It does not survive an operating-system restart, and the position-close request does not carry a broker idempotency key.

Production trading remains NO-GO.

`REAL_NETWORK_EXECUTION_NOT_TESTED`

`POSTGRESQL_INTEGRATION_NOT_TESTED`

`LINUX_INTEGRATION_NOT_VERIFIED`

R.74 was not started.
