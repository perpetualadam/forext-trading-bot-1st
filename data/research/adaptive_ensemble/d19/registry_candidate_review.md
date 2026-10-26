# Registry candidate review

The D.19 instruction names a candidate, `docker.io/library/python`, and a proposed tag, `3.12-slim-bookworm`. The same instruction says the candidate is not automatically approved.

The current Dockerfile contains `python:3.12-slim-bookworm` and no registry hostname. That text is compatible with the candidate and does not confirm it. A tag is mutable. No index digest, platform manifest digest, or provenance record was verified. No registry was contacted.
