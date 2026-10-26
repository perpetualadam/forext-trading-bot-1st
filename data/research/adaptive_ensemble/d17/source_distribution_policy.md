# Source distribution policy

The first reproducibility milestone should require compatible prebuilt wheels only. That is a planning preference. It does not authorise a download.

Source distributions and locally built wheels need a compiler toolchain. The Dockerfile does not install one. numpy, pandas, and a source build of the database driver would then depend on undeclared native packages. Provenance would include the compiler, headers, and build scripts, none of which are recorded.

A controlled build environment could be a later stage if a required wheel does not exist for the verified target. That stage would need its own toolchain inventory, network rules, and hash of the built wheel. It is not part of the first lock.

Hash verification applies to wheels and to any later built artifact. A missing wheel for the verified target stops the lock. It does not fall through to an unapproved source build.
