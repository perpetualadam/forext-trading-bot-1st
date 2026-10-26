# G.14.3 network and execution boundary

G.14.3 grants none of these permissions.

| Permission | Scope | Granted |
| --- | --- | --- |
| A | Read-only package metadata research | no |
| B | Download specified dependency artifacts | no |
| C | Verify downloaded artifacts | no |
| D | Create or modify candidate-specific packaging files | no |
| E | Execute a candidate Docker build | no |
| F | Export and inspect the resulting image | no |
| G | Run the candidate in an isolated test environment | no |
| H | Deploy or restart production | no |

A build that runs `pip install` can execute third-party installation hooks. That risk belongs to Permission E and must be stated again if E is ever requested.

Permission G is not a way to inspect packaging. Permission H is unrelated to a successful candidate build.

B and C are the evidence steps required before D or E can describe a locked offline build. A does not produce artifact hashes. E without B and C remains the unpinned network build.
