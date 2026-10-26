# Offline wheelhouse design

No wheelhouse was created.

A future wheelhouse needs the locked file name, size, and SHA-256 for every distribution in the closure, including transitive packages. Tags must match the verified target. The set must not contain extra packages, unapproved source distributions, or a wheel for a different Python or architecture.

The manifest itself needs a hash. Storage has to be separate from the production tree. Acquisition and install stay in different approvals. A mismatch quarantines the file and does not execute it.
