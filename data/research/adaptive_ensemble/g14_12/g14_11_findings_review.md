# G.14.11 findings preserved

Classification remains `G14_11_RECEIVER_DESIGN_COMPLETE_IMPLEMENTATION_BLOCKED`.

Preferred design remains `R1_DEDICATED_WINDOWS_PRINCIPAL_DESIGN_PREFERRED`. That preference is not enforcement.

Recorded and not refreshed by prohibited commands:

- Baseline and staging passed.
- No Docker, WSL, VM, network, download, or production change.
- No dynamic receiver test. Fifty adversarial scenarios were specified. Zero were executed.
- No Windows principal, receiving directory, ACL change, named pipe, or receiver program was created.

The proposed shape was a dedicated non-administrator account, a directory that account owns, a handle that account opens, a local pipe with SID checks, receiver-side verification, handle-bound publication, and a consumer that re-checks bytes.

Critical gaps G.14.11 left open, and that this stage treats as contract text rather than as facts:

1. The receiving principal does not exist.
2. The receiving directory does not exist.
3. ACL requirements were stated and not measured.
4. The ancestor chain was called out as necessary and was not specified ACE by ACE.
5. Same-user substitution resistance was not shown for any protected directory.
6. Sender and receiver authentication were requirements, not a message sequence.
7. Pipe-squatting resistance was not specified.
8. Publication immutability against file-ID reuse was not specified.
9. Executable and configuration integrity were not specified.
10. Implementation approval was not granted.

G.14.12 does not reinterpret the preferred design as a verified boundary.
