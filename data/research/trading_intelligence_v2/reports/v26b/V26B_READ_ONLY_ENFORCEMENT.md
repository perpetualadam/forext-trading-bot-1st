# V2.6B Read Only Enforcement

The standalone transport validates method, exact host, exact instrument path
and parameters before its sender. New LIVE-host fixtures verify POST/PUT/PATCH/
DELETE, account/order/position/trade/configuration routes, arbitrary hosts and
redirects are refused. No operational execution configuration is consulted.
No EXECUTION_MODE or trading gate is changed or relied upon for endpoint safety.

attempts=1 disables retries for429,503 and transport timeouts in the proposed
probe configuration. There is no account fallback or trading-loop startup.
One transport invocation does not paginate or poll. A caller can invoke it again;
a global single-use budget is NOT enforced by the current transport object.
A reviewed one-shot driver is therefore a prerequisite for a machine-enforced
one-request approval. No such authenticated driver was run.

The test sender is an injected synthetic seam; it does not prove live connectivity
or constrain arbitrary malicious Python outside the transport. No actual OANDA
REST request, with or without authentication, occurred in this stage.

No authenticated requests. Production remains NO-GO.
