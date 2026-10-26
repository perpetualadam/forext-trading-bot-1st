# Updated Gate B approval matrix

G.14.6 does not grant any permission. The offline controls are necessary before a later request. They are not that request.

| Permission | Scope | Status |
| --- | --- | --- |
| A | Package-index metadata requests | NOT GRANTED |
| B | Wheel-only resolution | NOT GRANTED |
| C | Wheel downloads | NOT GRANTED |
| D | Artifact verification | NOT GRANTED |
| E | Lockfile generation | NOT GRANTED |
| F | Candidate packaging | NOT GRANTED |
| G | Docker metadata | NOT GRANTED |
| H | Docker build | NOT GRANTED |
| I | Image export | NOT GRANTED |
| J | Isolated runtime test | NOT GRANTED |
| K | Production deployment | NOT GRANTED |
| L | Rollback | NOT GRANTED |

A future network request would still have to name hosts, port 443, redirect limits, the destination directory, size and time limits, wheels-only, no installation, and no credentials. This stage does not make that request.
