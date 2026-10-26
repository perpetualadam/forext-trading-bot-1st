# OFFLINE CLIENT INTEGRATION

D.30-R4 connects two existing results and does not open a transport.

The D.30-R1 client stops because standard-library name lookup is not hard-bounded. Its `discover` function raises before any socket. That classification stays `D30_R1_BLOCKED_CLIENT_SAFETY`.

The D.30-R3 supervisor can suspend a worker, place it in a Job Object, and confirm the worker handle exited. That was demonstrated with sleep fixtures. It does not cancel `getaddrinfo` inside an already running call.

The integrated client therefore has two separate duties:

1. Policy. Hosts, methods, digests, redirects, retries, and body ceilings are decided in the supervisor process. A policy acceptance is not a dispatch.
2. Refusal. `discover` raises `D30_R4_NETWORK_PATH_CLOSED` while name lookup remains unbounded. No socket object is constructed.

A synthetic worker can be placed in the D.30-R3 job wrapper to show the process boundary is wired. That worker writes a status line and exits. It is not an HTTP client.

Process termination and name-lookup cancellation remain different facts. This stage does not treat one as the other.
