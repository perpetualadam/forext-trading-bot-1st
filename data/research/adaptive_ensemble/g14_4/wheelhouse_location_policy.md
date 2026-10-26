# G.14.4 wheelhouse location policy

No wheelhouse was created.

## Future location

- Parent: the current user's temporary directory, from `tempfile.gettempdir()`.
- Name: `forext-g14-4-wheelhouse-` plus a unique suffix chosen in Gate B.
- On this machine the temporary parent is `C:\Users\Brian\AppData\Local\Temp`, which is outside OneDrive.
- The unique directory is not reserved and does not exist yet.

## Refusals

The destination helper rejects:

- a path inside OneDrive
- a path inside this repository
- the existing 63-file staging directory
- a directory that already contains files
- a symlink or reparse point
- path traversal and case-colliding names

It must not inherit files, live Docker volumes, operational state, or the shadow mount.

## Retention

Gate B, if approved, keeps the directory until a later cleanup names that exact path and its manifest. Gate A does not delete anything. The wheelhouse is not copied into the Docker context.
