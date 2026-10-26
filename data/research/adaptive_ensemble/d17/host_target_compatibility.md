# Host and target compatibility

D.16 recorded the host audit interpreter as Python 3.13.5 on Windows. This stage did not query installed packages and did not run a package manager. The container tag declares Python 3.12 on a Debian slim image.

The environments differ in Python minor version and operating system. Architecture, ABI, libc version, and wheel tags are not known for the target, so the size of the wheel mismatch cannot be measured here.

A lock produced from the host interpreter would select host markers and host wheels. That lock is not acceptable for the container. No host lock was generated.
