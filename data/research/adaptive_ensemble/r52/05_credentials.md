# Credential entry

`prompt_for_credentials` does not prompt when it is called with no readers. `launch` does not call it. Tests that replace hidden input and normal input with failures still see the disabled launch succeed.

When tests pass two in-memory readers, the prompts are the fixed lines `Account identifier: ` and `API token: `. The returned holder prints as `MemoryCredential()`. A reader failure becomes `R52_REJECTED` with neither value in the message. Values are not taken from the command line, the environment, `.env`, or the Windows credential store.

A later activation would have to pass the terminal's normal account reader and its hidden token reader into this function. That change is not in this file. Hidden input would still not protect against a compromised terminal, a debugger, process-memory inspection, or an automated tool.

The broker permission on a real token remains `UNKNOWN`. This program cannot make the token read-only.
