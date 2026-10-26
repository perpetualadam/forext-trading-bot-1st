# G.14.3 wheelhouse design

This is a procedure for a later stage. No wheelhouse was created. Every filename, version, and hash below is `UNKNOWN`. None of these markers is a verified hash.

## Acquisition, not installation

1. Source: the Python Package Index, `https://pypi.org/simple`, unless a later approval names a different index. No index was contacted.
2. Exact package versions: `UNKNOWN` for direct packages and `UNKNOWN` for transitive packages.
3. Expected wheel filenames: `UNKNOWN`.
4. Expected SHA-256 hashes: `UNKNOWN`.
5. Target Python: 3.12, taken from the mutable base tag. The base image's exact interpreter build is unverified.
6. Target platform: linux/amd64, from the G.14.2 image platform. Not rechecked.
7. Wheel compatibility tags: `UNKNOWN`. A later resolution must record tags such as the selected `cp312` and manylinux tags. Those tags are not asserted here.
8. Transitive dependencies: must be enumerated by the resolver. They must not be guessed from the nine direct lines.
9. Reject any file whose name is not in the approved manifest.
10. Reject source distributions unless a separate approval names that one file. The default is wheels only.
11. Reject a manifest entry with a missing hash.
12. Reject a file whose SHA-256 differs from the manifest.
13. Reject an index redirect to a host that was not approved.
14. The acquisition step downloads and hashes only. It must not run `pip install` and must not execute package hooks.
15. A second checker, which does not share the downloader's selection code, re-lists the directory and re-hashes every file.
16. Store the wheelhouse outside OneDrive, under a new directory in the user temp area. Do not put it in the 63-file staging directory.
17. Keep it until a separate cleanup approval names that directory and the manifest digest. Do not delete it with a broad recursive command.

## Final install shape, after the artifacts exist

A later candidate Dockerfile, not the production Dockerfile, would install only from that directory:

```text
pip install --no-index --find-links <wheelhouse> --only-binary=:all: --require-hashes -r <locked requirements>
```

That command is not runnable now. The wheelhouse path, lock path, and hashes are `UNKNOWN`.

`--prefer-binary` in the production Dockerfile is not an equivalent control. It still allows a source build.
