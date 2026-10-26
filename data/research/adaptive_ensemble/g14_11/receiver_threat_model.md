# Receiver threat model

Evidence available is G.14.8's same-user swap, G.14.10's unelevated medium token, and the absence of a receiver. Mitigations below are design rules. They are not observed enforcement. Residual risk stays until the adversarial tests run.

## 1. Accidental same-user interference

- Capability: a normal program renames a directory.
- Entry: any path the receiver opens.
- Impact: the handle binds to the wrong object.
- Mitigation: the sender supplies no path. The receiver directory must fail a medium-integrity rename test before use.
- Evidence: G.14.8 cases 1 through 3.
- Missing: the ACL test.
- Residual: the window remains until that test passes.
- Future test: scenarios A, B, and D.

## 2. Malicious same-user processes

- Capability: the same rename, on purpose, without elevation. Demonstrated.
- Entry: parent path, binary path, config path, consumer path.
- Impact: wheels and a success mark on the substitute, or a replaced receiver binary.
- Mitigation: separate SID, no sender-chosen path, SID checks on the pipe, binary directory under the same anchor rule.
- Evidence: G.14.8. This token is medium integrity.
- Missing: proof this user cannot write the future directory.
- Residual: critical until the test fails closed.
- Future test: A through F, K, M, N.

## 3. Other unprivileged local users

- Capability: write only where a DACL allows.
- Entry: the same paths.
- Impact: same as substitution if the DACL is loose.
- Mitigation: receiver DACL must not grant other users write. Not written.
- Evidence: none for other accounts.
- Missing: DACL bytes.
- Residual: unknown.
- Future test: K with a second non-admin token, if one exists. Creating one is a later approval.

## 4. Elevated administrators

- Capability: take ownership, change ACLs, replace binaries, reconfigure accounts.
- Entry: any host object.
- Impact: the receiver account can be taken over.
- Mitigation: none claimed.
- Evidence: this process is not elevated. The Administrators SID is deny-only on the token, which does not prove the account cannot elevate later.
- Missing: an elevation test. Not requested.
- Residual: out of the claimed defense. Not solved.
- Future test: L records elevated success as out of scope if it happens. Do not weaken production to try it.

## 5. Host compromise

- Capability: code execution as this user or higher.
- Entry: any of the above.
- Impact: receiver and trading host are both attacker-controlled.
- Mitigation: none claimed for a fully compromised host.
- Evidence: none that R1 survives it.
- Missing: an external root of trust. Not part of this design.
- Residual: out of scope.
- Future test: none that pretends to prove otherwise.

## 6. Guest compromise

- Capability: code inside a future VM, WSL distro, or container.
- Entry: the byte stream it sends.
- Impact: malicious wheels. Not a path, if the protocol is bytes only.
- Mitigation: the receiver still verifies bytes and refuses unapproved provenance. A shared folder would add the path bug. Shared folders are forbidden.
- Evidence: no guest exists.
- Missing: guest isolation from G.14.10.
- Residual: a guest is not selected.
- Future test: only after a guest approval. Not now.

## 7. Receiver compromise

- Capability: the receiver process runs attacker code.
- Entry: replaced binary or config.
- Impact: it can publish anything it writes.
- Mitigation: the binary directory must fail the same write test. Not shown.
- Evidence: no binary was installed.
- Missing: that test.
- Residual: high until M and N fail closed.
- Future test: M and N.

## 8. Sender compromise

- Capability: the allowlisted sender sends hostile bytes.
- Entry: the pipe.
- Impact: bad wheels, not a substituted directory, if the receiver ignores paths.
- Mitigation: independent verification and provenance refusal.
- Evidence: synthetic verifier exists. No live sender.
- Missing: an approved source.
- Residual: a hash does not make a source approved.
- Future test: AD through AL.

## 9. Malicious wheel metadata

- Capability: hostile METADATA or WHEEL text.
- Entry: the ZIP.
- Impact: wrong name, tag, or dependency.
- Mitigation: `inspect_wheel_bytes`. No code execution.
- Evidence: G.14.4 through G.14.8 helpers.
- Missing: a complete tag set.
- Residual: target profile incomplete.
- Future test: AE, AL.

## 10. Malicious dependency content

- Capability: a wheel that is structurally valid and still the wrong package.
- Entry: the bytes.
- Impact: the graph can be consistent and still untrusted.
- Mitigation: source approval, which is absent, plus hashes.
- Evidence: no approval.
- Missing: package-source approval.
- Residual: critical for any real download.
- Future test: AI.

## 11. Malicious package-index responses

- Capability: an index returns unexpected projects.
- Entry: a future HTTPS client. None exists.
- Impact: wrong set.
- Mitigation: the receiver does not contact an index. A sender that did would need a separate approval.
- Evidence: `NETWORK_DISABLED`.
- Missing: a sender.
- Residual: not reachable today.
- Future test: AI, without a live index in the receiver test.

## 12. Unapproved redirects

- Capability: a fetch follows a new host.
- Entry: that future client.
- Impact: bytes from the wrong host.
- Mitigation: provenance with an off-host URL fails. No socket in receiver tests.
- Evidence: no request in this stage.
- Missing: redirect handler tests against a non-network fixture.
- Residual: open for any future sender.
- Future test: AJ.

## 13. Path substitution

- Capability: G.14.8.
- Entry: `CreateFileW` on a writable path.
- Impact: wrong directory.
- Mitigation: no sender path. Unverified ACL.
- Evidence: level 1 race.
- Missing: receiver directory.
- Residual: the design is blocked on this.
- Future test: A through F.

## 14. Handle substitution

- Capability: the sender offers a handle.
- Entry: an API that accepts it.
- Impact: writes land in the sender's object.
- Mitigation: refuse sender handles.
- Evidence: design only.
- Missing: an implementation to test.
- Residual: open until Q is run.
- Future test: Q.

## 15. Reparse points

- Capability: junction now; symlink not created; other tags unknown.
- Entry: the opened object.
- Impact: the object is not a normal directory.
- Mitigation: reject the reparse attribute.
- Evidence: G.14.8 junction tests. Symlink errno 22.
- Missing: symlink kernel result and other tags.
- Residual: partial.
- Future test: G, H, I.

## 16. Credential leakage

- Capability: a name that is a backup or `.env` file, or a mounted profile.
- Entry: a filename or a host mount.
- Impact: broker or database secrets copied.
- Mitigation: reject those names and do not read them. The receiver account holds none. Not created.
- Evidence: staging excludes the names. Contents were not opened.
- Missing: proof a future process cannot see the user profile.
- Residual: high if the receiver runs as this user.
- Future test: AS.

## 17. Production mount exposure

- Capability: a destination under the bot's mounts.
- Entry: a path argument.
- Impact: production files change.
- Mitigation: the protocol has no destination path. Production paths are refused.
- Evidence: this stage wrote only G.14.11 documents.
- Missing: an implementation.
- Residual: process restraint today.
- Future test: AR.

## 18. Database exposure

- Capability: a connection to PostgreSQL.
- Entry: a connection string in the environment.
- Impact: live state changes.
- Mitigation: receiver environment must not contain it. Not read here. No connection.
- Evidence: no client was used.
- Missing: a measured empty environment for a future account.
- Residual: `LIVE_DATABASE_COMPATIBILITY_UNVERIFIED`.
- Future test: AU, without using the live server.

## 19. Broker API exposure

- Capability: any HTTP call to OANDA.
- Entry: inherited credentials plus network.
- Mitigation: no credentials and no request.
- Evidence: none were used.
- Missing: an enforced deny on a future host.
- Residual: process restraint only.
- Future test: AT, sink only, never OANDA.

## 20. Build-context contamination

- Capability: extra files enter a candidate context, or wheels are dropped into the 63-file tree.
- Entry: a copy step.
- Impact: the build sees unauthorised inputs.
- Mitigation: consumer receives bytes only; staging is frozen; unexpected names fail.
- Evidence: staging reverified unchanged.
- Missing: a consumer implementation.
- Residual: `RECEIVER_TO_BUILD_BOUNDARY_UNVERIFIED`.
- Future test: F, AQ, and the publication tests.
