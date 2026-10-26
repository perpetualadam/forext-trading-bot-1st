# R.49 broker-enforced permission assessment

Status: `UNKNOWN`.

No network lookup was made. Local non-secret source was searched for an OANDA token scope that the broker itself limits to read-only calls. Nothing in that source establishes such a scope for a v20 spread-betting account. Labels that say "read-only" elsewhere in the project refer to local displays and research notes, not to an OANDA token permission.

A program that sends only GET does not change what the token is allowed to do. An OANDA token may still be able to place orders. This stage does not claim the token is read-only.
