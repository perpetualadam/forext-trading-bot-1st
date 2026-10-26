# Broker-token permission

The permission on a real OANDA token is `UNKNOWN`.

R.48, R.49, and R.50 refuse order endpoints in this research process. That is a property of this code. It is not a property of an OANDA token. The public material reviewed earlier does not show that a token used for these two GET requests is prevented from creating or changing orders.

A future read-only claim would require evidence from the broker that the credential itself cannot trade. Until that evidence exists, the token must be treated as capable of trading even if this connector has no order method.

No real token was read, stored, or tested in R.50.
