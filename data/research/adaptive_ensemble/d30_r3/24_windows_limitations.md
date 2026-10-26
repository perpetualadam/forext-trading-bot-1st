# WINDOWS LIMITATIONS

- Supervisor already in a Job Object: True.
- Limit flags read back: 8200.
- Active process limit read back: 1.
- Breakaway bits were clear in the readback: True.
- A third fixture process was not created. The active-process limit was configured and read back. While a descendant was alive, the job also contained conhost.exe members, so that limit is not proof that the job holds only two processes.
- Job handles were not placed in the inherited handle list.
- CloseHandle on the job was tested separately from TerminateJobObject.
- Windows version observed through sys.getwindowsversion: 10.0.26200.
- Process pointer width: 8 bytes. This is not a Python ABI measurement.
- libc was not measured.
- These results belong to this Windows process. They are not a universal Windows guarantee.
