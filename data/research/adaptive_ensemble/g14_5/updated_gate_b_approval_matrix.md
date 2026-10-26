# Updated Gate B approval matrix

G.14.5 grants none of these permissions. Real downloads are not requested while findings G14.5-01 through G14.5-07 remain open.

| Permission | Scope | Status |
| --- | --- | --- |
| A | Read-only package-index metadata | NOT GRANTED |
| B | Target-specific wheel-only resolution | NOT GRANTED |
| C | Download of selected wheels | NOT GRANTED |
| D | Independent hash and metadata verification | NOT GRANTED |
| E | Candidate dependency lock | NOT GRANTED |
| F | Candidate packaging changes | NOT GRANTED |
| G | Docker metadata verification | NOT GRANTED |
| H | Candidate Docker build | NOT GRANTED |
| I | Candidate image export | NOT GRANTED |
| J | Isolated candidate runtime testing | NOT GRANTED |
| K | Production deployment | NOT GRANTED |
| L | Rollback | NOT GRANTED |

Any later network permission must name hosts, protocol, port, redirect limits, the download directory, size and time limits, wheels-only, no installation, no source builds, no credentials, and the stop conditions. It must not be a blanket network allowance.
