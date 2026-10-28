# Credential boundary

`ExistingOandaCredentialProvider` implements the existing `credential()` delivery
interface but always raises `AUTHENTICATED_EXECUTION_DISABLED`. It has no loader,
callback, enable flag or stored token. Configuration-key metadata names only
`TRADING_MODE`, `OANDA_ACCESS_TOKEN` and `OANDA_API_KEY`; no values are read.
The adapter's `acquire_history` delegates to the existing disabled gate before
calling a provider or opening storage/network resources.

Synthetic tests use the existing exact `SyntheticCredentialProvider` class.
Other providers, including the disabled future interface and subclasses, are not
accepted by the controller. A grant is durably reserved before its memory-only
credential is requested. Existing bounded anonymous-pipe delivery and process
fencing remain unchanged. No token travels in worker argv, URLs, environment,
report/manifest metadata or arbitrary headers supplied by a caller.

Worker responses contain bounded fixed status/type information. Arbitrary provider
or transport exception bodies are not returned. Provider representations redact
values. Tests cover provider exceptions, token echo rejection, process arguments,
environment, safe request records and every synthetic archive file. No token
erasure guarantee is claimed for Python/process memory.

No real credential source was accessed: no dotenv file, environment token getter,
Windows Credential Manager, operational API Session or production credential
file. Tests inspect operational source as text only. The real provider, LIVE
worker permission and real grant schema require separate review/authorisation;
this commit publishes no live-token loader or executable authenticated entry.
