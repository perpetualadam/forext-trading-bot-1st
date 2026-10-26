# Resolution repeatability

A later stage can test repeatability only after the target profile and resolver version are fixed.

Run the same resolver twice with the same requirements hash, the same markers, the same index snapshot or the same already verified artifact set, and the same artifact-selection rule. Compare lock bytes after a defined normalization, then compare selected versions and artifact hashes.

That result would support reproducible resolution. It would not prove reproducible installation. Installation still needs the wheelhouse, hash checks, and an offline install. An image build is a third claim and needs the base-image digest and the Dockerfile inputs as well.
