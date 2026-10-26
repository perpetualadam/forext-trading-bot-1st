# G.14.4 network and execution boundary

Gate A performed none of these.

| Step | What it is | Gate A | Implied by a later download |
| --- | --- | --- | --- |
| A | Read package metadata | no | no |
| B | Download wheel bytes | no | only if that download is separately approved |
| C | Hash those bytes | no | yes, as the check on B |
| D | Parse wheel metadata without running code | no | no |
| E | Install wheels | no | no |
| F | Run installation hooks | no | no |
| G | Build source distributions | no | no |
| H | Run application code | no | no |

A download approval does not allow install, hook execution, source builds, Docker, or the forex application.
