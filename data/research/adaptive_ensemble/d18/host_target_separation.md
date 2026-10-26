# Host and target separation

D.17 recorded the host audit interpreter as Python 3.13.5. That remains a historical observation. This stage did not query installed packages.

The audit commands ran on Windows. That fact identifies the workstation used for the audit. It does not identify the deployment target. Host CPU architecture was not measured. G.14.2 recorded a historical Docker Desktop environment as `linux/amd64`. That record is a past daemon observation and is not a current host or target measurement.

Target evidence is the Dockerfile tag: Python 3.12 and a Debian bookworm indicator. Target architecture, ABI, and libc version are missing.

Host interpreter, host OS, and host architecture are not inputs to dependency resolution. Target implementation, minor version, patch, OS, architecture, ABI, and libc are inputs. Host compatibility does not imply target compatibility. No host wheel tags and no host lock were generated.
