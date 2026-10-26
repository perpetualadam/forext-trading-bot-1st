# HTTPS adapter

`https_adapter.py` is a standard-library module. It does not import `forex_bot`. It does not read the environment. It does not call `getpass` or `urlopen`.

`tls_context` builds `ssl.create_default_context` for server authentication and refuses the context unless certificate verification is required and hostname checking is on. The adapter never assigns a bypass.

`exchange` accepts one prepared GET from the R.50 connector. It checks the host, the method, the two path templates, the six-name filter, the pricing conversion flag, a five-second timeout, zero retries, redirects off, an empty body, and streaming off. It then asks an injected connection factory for one connection, sends one GET, and accepts only status 200. A redirect is not read and not followed. A factory error is not retried. The body is decoded once, in memory, with a one-megabyte cap.

The real `http.client.HTTPSConnection` class is refused by identity. `blocked_factory` raises `R51_LIVE_TRANSPORT_DISABLED`. No constant is consulted to choose a live factory. `launch` never calls `exchange`. A flag, environment variable, confirmation phrase, or edited constant in the existing switches cannot start traffic, because those switches only raise.

A later stage would have to add a new factory that constructs the real connection. That line is not in this file.

`run_offline` sends the two R.50 reads through `exchange`, keeps a budget of two calls, parses the allowlisted fields, and attaches `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED`. Raw payloads are dropped before the result is returned. The result is refused if it contains the account identifier, the token, `Bearer`, `Authorization`, `https://`, or `1.35`.
