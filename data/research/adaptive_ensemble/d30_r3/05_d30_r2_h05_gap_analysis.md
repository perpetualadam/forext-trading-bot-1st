# D.30-R2 H05 GAP

D.30-R2 classification remains `D30_R2_OFFLINE_SUPERVISOR_VALIDATED`.

Its cleanup record H05 remains `NOT_EVALUATED`. That record is not a pass. D.30-R2 ran 59 synthetic records, 58 passed, and 0 failed. The unevaluated record is descendant-process containment.

D.30-R2 terminated a worker with `TerminateProcess` on the worker handle and confirmed that handle with `poll`. The same call does not apply to a process the worker creates. D.30-R2 did not spawn a grandchild, because an uncontained grandchild would have made cleanup uncertain. No Job Object was used.

The E04 block fixture in D.30-R2 used a synthetic operation deadline of 0.35 seconds. The measured total elapsed time was 0.534 seconds. That total includes termination. It is not evidence that cleanup finished inside the operation deadline, and it is not evidence about a descendant.

D.30 and D.30-R1 remain `D30_BLOCKED_PROMPT_INTEGRITY` and `D30_R1_BLOCKED_CLIENT_SAFETY`. Neither stage is reclassified here. The D.30-R1 synthetic resolver was still running when its caller returned. A process-tree result does not cancel that DNS finding and does not authorise a registry request.
