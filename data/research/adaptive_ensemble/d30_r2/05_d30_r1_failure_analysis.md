# D.30-R1 FAILURE ANALYSIS

D.30 stopped with D30_BLOCKED_PROMPT_INTEGRITY because the requirements.txt expected digest had 66 hexadecimal characters. No network request was made.

D.30-R1 corrected that digest and then stopped with D30_R1_BLOCKED_CLIENT_SAFETY. Its synthetic resolver was still running when the caller stopped waiting, and the resolver was not cancelled.

Returning from a timed wait, cancelling the blocking call, terminating the worker, and confirming that the worker exited are four different events. D.30-R1 showed only the first. D.30-R2 tests the third and fourth on local sleep fixtures. It does not cancel real DNS.
