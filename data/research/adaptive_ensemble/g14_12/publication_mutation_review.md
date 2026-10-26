# Publication and post-verification mutation

Classification: `ARTIFACT_PUBLICATION_BOUNDARY_UNVERIFIED` and `POST_VERIFICATION_MUTATION_PROTECTION_UNVERIFIED`.

## Invariant

No artifact is consumable unless a publication record written with `FILE_CREATE` on the receiver's still-open directory handle binds the exact bytes the receiver just re-read, their SHA-256 and size, the approved provenance, the lock identity, and the target-profile identifier, and the consumer receives those bytes over the authenticated pipe and verifies them again before use.

The invariant is not enforced. Nothing was published.

## The 25 questions

1. A commit record can be forged by anyone who can create a file in the directory. The interactive user must not be able to. The receiver SID can. A forged record from the interactive user fails the DACL test, which is unverified. A record not produced in the legal state order is not a commit.
2. Replacement of the record is a new create. Exclusive create refuses an existing name. Deleting it requires DELETE, which the interactive SID must not have.
3. Verified bytes can change if a writer can open the file. The interactive SID must not. The receiver re-reads the open handle before commit and before send. A mismatch fails.
4. Another receiver session is refused while one session is active.
5. A consumer sees bytes only after the commit exists and the re-read matches. A partial transfer has no commit.
6. A crash between verification and commit leaves no commit. Recovery does not invent one.
7. A crash after a complete commit leaves the record. The next process may serve it only if it is the receiver SID, the file index and hash still match, and the directory handle is held again after a fresh ancestor check. If any check is unknown, it does not serve.
8. A consumer that opens a path can be substituted. The consumer has no path.
9. The receiver must not reopen the published object by a path supplied by anyone else. After close, the session is not consumable until the receiver opens its own directory again under the ancestor contract.
10. The consumer must not reopen by path.
11. A file index can be reused after deletion. The index is not sufficient.
12. File index plus hash is not sufficient after the handle is closed, for the same reason. The open handle plus a fresh read is required at send time.
13. Immutable storage is not available as a measured feature. It is not claimed.
14. Copy-on-publish into a user directory is forbidden. The publish step is the commit record on the receiver handle.
15. A separate published namespace is not required if the commit rule and the single-session rule hold. A second writable tree would be a second ancestor problem.
16. Consumer access is the pipe, not a handle duplicated from the interactive user.
17. Consumer verification is after the bytes arrive, on those bytes.
18. Source approval is a field in the commit. Empty approval means no commit.
19. Lock identity is a field in the commit. A synthetic marker cannot be that field's success value.
20. Target profile identifier is a field in the commit. Unknown tags mean no commit.
21. Post-publication writes by the interactive user must fail the DACL. Writes by a compromised receiver are outside the claim.
22. Recovery treats a missing or truncated commit as incomplete. It does not delete historical evidence outside the prototype.
23. Audit records live on the receiver handle. If that handle's disk is lost, the audit is lost. No second copy into the repository is authorised.
24. Cleanup must not delete the staging tree, probe directories, or production files.
25. Publication must not write production, operational, or shadow paths. Those destinations are refused.

G.14.8 post-open binding remains the only related empirical result, and it was on a directory this user could already replace before the open.
