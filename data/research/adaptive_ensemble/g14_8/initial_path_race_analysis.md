# G.14.8 initial path race

## Answers

1. The path opened is the caller-supplied parent directory. In the workflow that is the pytest temporary directory, or a prohibited path rejected before the open.
2. The user who owns that temporary directory controls it.
3. The same user can control parent components of a path under the user profile or TEMP.
4. A component can be replaced. The pre-open test renamed the intended directory away and moved a decoy onto the same path.
5. A junction can be inserted. A junction used as the open path was rejected only because the opened object itself was a reparse point. A junction above an unopened path was not given a separate trust anchor.
6. A directory symlink could not be created (`errno` 22). It was not shown to be rejected by the kernel.
7. A parent can be renamed after its handle is open. Later writes stayed on the handle.
8. A directory can be replaced between `os.lstat` and `CreateFileW`. The open then returned the replacement.
9. The open requests `FILE_FLAG_OPEN_REPARSE_POINT`. A junction was not followed; it was rejected. That is not proof for every reparse tag.
10. The returned handle can be identified by volume serial and file index. That identity is the opened object, not the previously intended object.
11. The handle cannot be tied to a trusted parent. It is the first handle in the chain.
12. The initial open cannot be eliminated in this design. There is no inherited trusted handle.
13. Create-new semantics apply to the child, not to the parent open. They do not contain the parent race.
14. Retained handles contain operations after the open. They do not contain the open.
15. A same-user process can interfere. The swap did not require another user or an administrator.
16. The workflow cannot detect that pre-open substitution. It will write on the substitute and can still report `COMPLETE_SYNTHETIC`.
17. Prohibited locations are rejected by path policy before create. A substitute inside an allowed test directory is not detected.
18. After the handle exists, artifact and lock operations do not reopen by path.
19. A filesystem race remains: the initial pathname lookup.
20. The justified claim is only that, once a non-reparse directory handle has been obtained, later creates and reads in this helper use that handle. It is not a claim that the handle is the directory the caller intended.

## Classification

`INITIAL_PATH_RACE_UNVERIFIED`

`INITIAL_PATH_RACE_ELIMINATED` does not apply. `INITIAL_PATH_RACE_CONTAINED_WITH_ASSUMPTIONS` does not apply either: the same-user assumption required to trust the path is the assumption the swap disproved.
