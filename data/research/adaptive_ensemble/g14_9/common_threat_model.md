# Common threat model

The same attacker list is applied to Option A (same-user launcher), Option B (an isolation boundary that has not been selected), and Option C (the same user declared trusted). Evidence is local: G.14.8 race results, `open_directory` in `tests/g14_7_fs.py`, and `DEFAULT_TRANSPORT = NETWORK_DISABLED` in `tests/g14_7_transport.py`. No option is implemented.

Elevated administrators and a fully compromised host are outside every claim. Nothing in the repository shows a boundary against those two.

## A. Accidental concurrent filesystem change

- Capability: another program renames or replaces a directory without hostile intent.
- Entry: the parent path before `CreateFileW`, or an export path on the way out.
- Impact: the handle, or the imported bytes, refer to the replacement.
- Mitigation: A retains the handle after open, which covers only the post-open window. B could contain the accident only inside an unproven boundary. C accepts the race.
- Assumption: none that removes the pre-open window.
- Evidence: G.14.8 cases 1 through 5.
- Missing: a pre-open control.
- Residual: the pre-open window remains for A and C. For B it is unknown.

## B. Malicious same-user process

- Capability: rename a user-owned directory. Demonstrated without elevation.
- Entry: caller-supplied parent path, launcher path, export path, or a virtual-disk path if the same user can write it.
- Impact: artifacts and a success marker land on the substitute.
- Mitigation: not provided by A or C. B is the only design class that might, and only if the boundary is not this user's to rewrite. That condition is not evidenced.
- Assumption: C assumes this actor is benign. That assumption contradicts the demonstration.
- Evidence: G.14.8 cases 1, 2, 3, and 11. `same_user_resistance` is `FAILED`.
- Missing: a principal this user cannot impersonate.
- Residual: critical for A and C. Unknown for B.

## C. Other unprivileged local users

- Capability: modify an object only if its DACL grants them write.
- Entry: parent path or export path.
- Impact: same as a substitution if the DACL allows it.
- Mitigation: not measured.
- Assumption: none. A user-owned DACL was not read.
- Evidence: none for other accounts. `ACL_RESTRICTION_UNVERIFIED`.
- Missing: DACL contents and a cross-user test.
- Residual: unknown. Not a reason to ignore the same-user result.

## D. Elevated local administrators

- Capability: change DACLs, replace files, debug processes, mount volumes.
- Entry: any path or process on the host.
- Impact: full control of host-side acquisition.
- Mitigation: none claimed.
- Assumption: administrators are outside the model for every option.
- Evidence: not tested, and elevation was not requested.
- Missing: not applicable inside this model.
- Residual: accepted as out of scope, not as solved.

## E. Host compromise

- Capability: code execution as this user or higher.
- Entry: any of the above.
- Impact: the acquisition result and the trading host are both attacker-controlled.
- Mitigation: none claimed. A guest does not repair a compromised hypervisor owner.
- Assumption: a fully compromised host is outside the claim.
- Evidence: none that any option survives it.
- Missing: an external root of trust. Not available in this review.
- Residual: out of scope, not solved.

## F. Malicious reparse point

- Capability: place a reparse point on a path that will be opened.
- Entry: parent path before open, or a child name if create followed the reparse.
- Impact: the opened object is not the directory the path suggests.
- Mitigation: `FILE_FLAG_OPEN_REPARSE_POINT` on the parent open, and rejection when `FILE_ATTRIBUTE_REPARSE_POINT` is set. Child creates also request `FILE_OPEN_REPARSE_POINT` for directories.
- Assumption: the attribute check sees every relevant tag. The tag list was not enumerated.
- Evidence: a real junction was rejected. Other tags were not.
- Missing: directory symlink (errno 22, not executed) and other tags.
- Residual: partial. The attribute check is real for the junction that was tested. It is not a complete reparse proof.

## G. Junction substitution

- Capability: `mklink /J` inside a directory this user can write. No administrator was required for the G.14.8 junction test.
- Entry: parent path before open, or the old path after open.
- Impact: before open, the junction is the opened object and is rejected. After open, writes stayed on the original object.
- Mitigation: the reparse-attribute rejection and the retained handle.
- Assumption: junction behaviour on this machine matches the test.
- Evidence: G.14.8 cases 7 and 8.
- Missing: junctions on a volume type that was not tested.
- Residual: low for the tested NTFS case, after the object is opened. The pre-open junction is rejected rather than followed, in the tested case.

## H. Directory-symlink substitution

- Capability: create a directory symlink. On this machine `os.symlink` failed with errno 22.
- Entry: parent or child path.
- Impact: unknown kernel behaviour for this helper.
- Mitigation: the same reparse-attribute check would apply if the open returned an object with that attribute. That was not executed for a symlink.
- Assumption: none. Injected `lstat` results are not kernel proof.
- Evidence: skipped test, errno 22.
- Missing: a real directory symlink.
- Residual: `UNVERIFIED` for every option.

## I. Parent-directory replacement

- Capability: rename the parent aside and put another directory at the same path.
- Entry: before `CreateFileW`, or after it.
- Impact: before, the substitute receives the child. After, the handle stays on the original object.
- Mitigation: post-open retention only.
- Assumption: C treats the replacer as trusted.
- Evidence: G.14.8 cases 1 through 5.
- Missing: a pre-open prevention.
- Residual: critical before the open.

## J. Pre-open path substitution

- Capability: same as I, specifically in the window the code cannot see.
- Entry: `open_directory` and any future launcher or importer that uses a path.
- Impact: wrong trust anchor for every later handle-relative call.
- Mitigation: none in the current code. A moves the window. B might remove it only with an unevidenced boundary. C accepts it.
- Assumption: a file id taken after the open is not a pre-open identity.
- Evidence: G.14.8 independent re-audit, `race_resistance` = `FAILED`.
- Missing: an anchor established before the untrusted user can schedule the swap.
- Residual: this is the blocking finding.

## K. Post-open path substitution

- Capability: change the path after the handle exists.
- Entry: the original path string.
- Impact: none on later creates in the tested rename and junction cases.
- Mitigation: `RootDirectory` creates. The path is not reused for those creates.
- Assumption: the tested sharing mode and NTFS behaviour hold for the volumes in use.
- Evidence: G.14.8 cases 4, 5, and 8. `post_open_binding` = `VERIFIED`.
- Missing: cross-volume and symlink cases.
- Residual: low for the tested operations. This does not repair finding J.

## L. Untrusted wheel metadata

- Capability: a hostile index or wheel claims a name, version, dependency, or tag.
- Entry: metadata parsed before bytes are verified.
- Impact: wrong dependency set, or a parser bug. Not a directory-identity bug.
- Mitigation: the synthetic workflow checks names, hashes, and wheel structure on bytes it received through the injected transport. No real index was contacted.
- Assumption: the synthetic checks are what a future sender would have to meet. They are not a live control yet.
- Evidence: G.14.7 integration still reached `COMPLETE_SYNTHETIC` only on synthetic bytes.
- Missing: a real index response.
- Residual: unchanged until a sender exists. The directory race is independent of it.

## M. Malicious package-index responses

- Capability: the index returns unexpected projects or URLs.
- Entry: a future HTTPS response.
- Impact: dependency confusion or an unapproved host.
- Mitigation: no sender exists. `NETWORK_DISABLED` fails closed for a live request.
- Assumption: a future policy would pin the index host and reject extra indexes.
- Evidence: transport default and the absence of a live sender.
- Missing: an approved host and a tested sender.
- Residual: not reachable today. Not approved for later.

## N. Unapproved redirects

- Capability: an index or artifact response redirects elsewhere.
- Entry: a future HTTP stack.
- Impact: bytes fetched from a host that was not approved.
- Mitigation: none implemented, because no request is sent. The synthetic policy is not a live redirect handler.
- Assumption: none about live redirect behaviour.
- Evidence: no live request in G.14.8 or G.14.9.
- Missing: a sender test against a local, non-network redirect fixture would still be a later stage.
- Residual: open for any future sender.

## O. Dependency confusion

- Capability: a similarly named package on an index the resolver consults.
- Entry: index selection.
- Impact: the wrong wheel is verified and locked.
- Mitigation: the synthetic selector uses the injected document only. No second index is configured in a live resolver because no live resolver ran.
- Assumption: a future design keeps one approved index and rejects direct URLs and VCS.
- Evidence: synthetic workflow only.
- Missing: an approved index and a complete production graph. `DEPENDENCY_GRAPH_COMPLETENESS_UNVERIFIED`.
- Residual: open.

## P. Credential exposure

- Capability: read this user's profile, the two backup filenames, or a broker token if one is reachable.
- Entry: a mount, a child process environment, or a path walk.
- Impact: broker or database credentials leave the host.
- Mitigation: this stage did not open the backup files. Destination checks reject the repository and those filename categories when they appear as member names. A same-user process is not stopped by that check.
- Assumption: B would have no host profile mounted. Unevidenced.
- Evidence: staging verifier rejects `.env` names and the two backup names inside the 63-file tree. That tree is not an acquisition sandbox.
- Missing: proof a future environment cannot see the user profile.
- Residual: high if acquisition runs as this user. The backup files were not read.

## Q. Network egress to unauthorised hosts

- Capability: open a socket to any host.
- Entry: a future sender, or a package build hook.
- Impact: download, exfiltration, or OANDA contact.
- Mitigation: no sender, and this stage made no request. Package hooks must not run during acquisition.
- Assumption: a future environment would default to deny. Not observed.
- Evidence: `NETWORK_DISABLED`.
- Missing: an enforced network boundary.
- Residual: the application flag is not an OS boundary.

## R. Production filesystem exposure

- Capability: read or write the repository or the running bot's files if the same user can.
- Entry: a mount or a path that escapes the destination checks.
- Impact: production source or runtime files change.
- Mitigation: destination denylist. Not a mandatory access control. This stage changed no production Python.
- Assumption: B would not mount the repository. Unevidenced.
- Evidence: denylist in `assert_destination_boundary`. G.14.9 modified no production file.
- Missing: an OS boundary.
- Residual: the denylist is bypassed if the open is pointed at a substitute that itself contains or links further. The helper rejects reparse on the opened directory in the tested junction case.

## S. Operational-state exposure

- Capability: open operational safety state.
- Entry: a path whose components include the blocked names, or a substitute outside the denylist.
- Impact: live-order authorisation or the block reason could change if those files were written.
- Mitigation: this stage did not read or write them. The denylist names them.
- Assumption: the files remain untouched. That is an action constraint, not a proven kernel policy.
- Evidence: no access in this stage.
- Missing: an OS denial a same-user process cannot lift.
- Residual: process restraint only.

## T. Shadow-state exposure

- Capability: open shadow-state mounts.
- Entry: same pattern as operational state.
- Impact: shadow evidence changes.
- Mitigation: not accessed. Denylist includes `shadow_state` and `shadow-state`.
- Assumption: same as S.
- Evidence: no access.
- Missing: same as S.
- Residual: process restraint only. `SHADOW_MOUNT_COMPATIBILITY_UNVERIFIED` stays.

## U. Live database exposure

- Capability: connect to PostgreSQL.
- Entry: a connection string in the user environment, or a guest that inherited it.
- Impact: live trading state changes.
- Mitigation: no connection was opened. A future environment would have to lack the address and the secret.
- Assumption: unevidenced for B.
- Evidence: no database call in this stage.
- Missing: proof of network and secret isolation.
- Residual: `LIVE_DATABASE_COMPATIBILITY_UNVERIFIED`.

## V. OANDA API exposure

- Capability: any HTTP call to the broker, including GET.
- Entry: inherited credentials plus network.
- Impact: orders, positions, or account data.
- Mitigation: no broker call was made. Strategies were not started.
- Assumption: a future guest has neither credentials nor a route.
- Evidence: no call.
- Missing: an enforced deny.
- Residual: process restraint only.

## W. Unsafe artifact export

- Capability: swap the exported tree before the host hashes it, or include a reparse point in the export.
- Entry: the host open of the export path.
- Impact: the host verifies the attacker's bytes, or follows a link out of the tree.
- Mitigation: not implemented. A guest-side hash does not bind the host open.
- Assumption: B would need an export medium this user cannot replace. Unevidenced.
- Evidence: G.14.8 pre-open swap is the same shape as an import open.
- Missing: a tested export protocol.
- Residual: critical at the import boundary for every option that ends on a user-writable path.

## X. Host-side verification bypass

- Capability: present a manifest whose hashes do not match the bytes, or present the right hashes of the wrong intended set.
- Entry: a receiver that trusts the producer manifest.
- Impact: a false pass, or a pass on substituted-but-hashed bytes.
- Mitigation: the design in `artifact_export_import_protocol.md` requires the receiver to hash the bytes it reads. A matching hash still does not prove source approval or directory intent.
- Assumption: the receiver is actually run. It was not built.
- Evidence: synthetic verification already hashes handle-read bytes. That is not an import protocol.
- Missing: an implementation and a test.
- Residual: a hash match is not provenance.

## Y. Artifact replacement after verification

- Capability: replace a file after the hash and before the consumer opens it.
- Entry: any path-based handoff after verification.
- Impact: the consumer reads different bytes than the verifier hashed.
- Mitigation: keep the verified file handle, or publish through a boundary the replacer cannot write. A path rename between two user-writable directories does not provide that.
- Assumption: none for a same-user publisher.
- Evidence: post-open handle binding holds only while that handle is the one used for the read.
- Missing: an atomic publication anchored outside the attacker's write set.
- Residual: critical if verification and use are different path opens.

## Z. Supply-chain provenance gaps

- Capability: unknown patch level, unknown wheel tags, unapproved index, no lock, no wheelhouse.
- Entry: any future real resolution.
- Impact: a verified archive can still be the wrong build for the production image.
- Mitigation: none completed. The gaps are preserved on purpose.
- Assumption: none that fills them in.
- Evidence: G.14.8 blockers and the historical image id, which is not a registry digest.
- Missing: package-source approval, lock, wheelhouse, SOABI, glibc, pip, registry digest.
- Residual: deployment remains NO-GO for every option.
