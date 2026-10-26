# Preview, confirmation, and credential entry

The intended order inside `run_session` is fixed.

1. Build the non-sensitive preview.
2. Ask the injected confirmation reader to accept that preview.
3. Any answer other than `CONFIRM PREVIEW` returns immediately. Credential readers are not called and no client is constructed.
4. Refuse the live HTTPS and HTTP client classes before asking for credentials.
5. Ask the account-identifier reader with `Account identifier: `.
6. Ask the token reader with `API token: `.
7. Keep both values on a `MemoryCredential` object. Its text form is `MemoryCredential()`.
8. Call the pinned R.53 connector for at most two GET requests.
9. Write a file only when all three counters are 2.

Calling `prompt_for_credentials` without readers raises `R55_LIVE_TRANSPORT_DISABLED` and does not call `input` or a hidden-input function. A reader exception becomes `R55_REJECTED` with no original message.

The default command does not call `run_session`. Arguments, environment variables, `.env` files, and the Windows credential store are not read. The local confirmation text does not open a connection by itself.

Hidden input, if a later program passes it as the token reader, does not protect the token from a compromised terminal, a debugger, process-memory inspection, or other software on the machine. The token may still be allowed to trade. This connector does not establish that permission. It remains `UNKNOWN`.
