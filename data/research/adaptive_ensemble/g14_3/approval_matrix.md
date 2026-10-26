# G.14.3 approval matrix

No permission below is granted.

| Permission | Requested now | Granted | Notes |
| --- | --- | --- | --- |
| A. Read-only package metadata | no | no | Cannot produce artifact hashes. |
| B. Download specified artifacts | no | no | Required before a lock can be honest. Target would be CPython 3.12, linux/amd64. Versions are still `UNKNOWN`. |
| C. Verify downloaded artifacts | no | no | Separate from the download. |
| D. Candidate packaging files | no | no | Write them only after B and C. Do not edit the production Dockerfile or `requirements.txt`. |
| E. Docker build | no | no | Includes third-party installation hooks if pip runs. |
| F. Image export and offline inspection | no | no | New archive only. Do not recreate the G.12 archive. |
| G. Isolated runtime test | no | no | Not a packaging inspection. |
| H. Production deploy or restart | no | no | Remains NO-GO. |

Build approval: not granted.
Production deployment: NO-GO.
Rollback: NO-GO.
