# Credential entry

`prompt_for_credentials` raises `R53_LIVE_TRANSPORT_DISABLED` when no readers are supplied. `launch` does not call it. Tests that replace hidden input and normal input with failures still see the disabled launch succeed.

Injected readers receive the fixed prompts `Account identifier: ` and `API token: `. The holder prints as `MemoryCredential()`. A reader failure becomes `R53_REJECTED` without either value. Nothing is read from the command line, the environment, `.env`, or the Windows credential store.

A later approval would have to pass the terminal's account reader and its hidden token reader. Hidden input would not protect against a compromised terminal, a debugger, process-memory inspection, or malicious software.

Broker token permission remains `UNKNOWN`. This connector cannot make a token read-only.
