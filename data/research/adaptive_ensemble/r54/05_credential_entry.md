# Credential entry preparation

`prompt_for_credentials` is ready for a later session and was exercised only with synthetic readers.

- The account identifier reader is called with `Account identifier: `.
- The token reader is called with `API token: `.
- Both values stay on a `MemoryCredential` object. `str` and `repr` of that object are `MemoryCredential()`.
- Missing readers raise `R54_LIVE_TRANSPORT_DISABLED` and do not call `input` or a hidden-input function.
- A reader exception becomes `R54_REJECTED` with no original message.
- The preview and the written result are rejected if they contain either value, `Bearer`, `Authorization`, or `https://`.
- Arguments, environment variables, `.env` files, and the Windows credential store are not read.

The default command does not call this function. Hidden input, if a later program uses it, does not protect the token from a compromised terminal, a debugger, process-memory inspection, or other software on the machine. The token may still be allowed to trade. This connector does not establish that permission. It remains `UNKNOWN`.
