# Later Python and libc verification

After image identity exists, a separate approval is still required to establish the Python implementation, the 3.12 patch, the ABI, the Debian revision, the libc family, the libc version, native libraries, and wheel requirements.

A manifest can identify an image without exposing those runtime properties. Manifest inspection alone does not prove the Python patch or the libc version. If labels omit them, metadata inspection needs its own approval. No container is run in D.19.
