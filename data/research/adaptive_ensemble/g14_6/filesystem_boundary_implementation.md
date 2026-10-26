# Filesystem boundary

`assert_destination_allowed` no longer uses `Path.resolve` on the candidate. It rejects `..`, repository paths, OneDrive, the Consensus Forecast directory name, Docker volume path fragments, the staging directory, operational-state names, symlinks, and reparse points. Parents are checked with `os.lstat` so a link is not followed. Case-colliding names are rejected.

`create_exclusive_file` uses `O_CREAT|O_EXCL` and does not report success after a short write. A second write to the same name is rejected. No real wheelhouse was created.

A concurrent replacement of a parent directory between the check and a later write is still possible. The plan records `ACQUISITION_FILESYSTEM_BOUNDARY_UNVERIFIED` for that residual window. The original defect, following a link via `resolve`, is closed on the acquisition path.
