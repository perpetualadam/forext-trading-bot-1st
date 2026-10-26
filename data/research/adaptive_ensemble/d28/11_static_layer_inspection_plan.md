# STATIC LAYER INSPECTION PLAN

This plan was not executed.

The preserved manifests identify compressed layer blobs. The preserved configs identify uncompressed rootfs diff IDs. Those digest types are different and must not be substituted for each other.

A future static inspection would need, in order: digest-verified compressed blobs, a bounded decompress step, a verified uncompressed diff ID, and a sandbox that never extracts directly onto the host filesystem.

The sandbox must reject path traversal, unsafe symlink and hardlink targets, and device files. It must bound file counts, individual file sizes, and total extracted size. Whiteouts and opaque directory markers must be applied in manifest order when reconstructing a root, and that reconstruction is a separate approval from merely downloading blobs.

Interpreter and libc files would then be located by path and ELF headers. ELF class, machine, PT_INTERP, and symbol-version tables can be read without executing the files. A version string inside a shared object is still a file observation, not loader behaviour.

Static inspection cannot establish live sys.platform, sys.version, effective library search, or the wheel tags an interpreter process will accept.

No layer was downloaded or extracted in D.28.
