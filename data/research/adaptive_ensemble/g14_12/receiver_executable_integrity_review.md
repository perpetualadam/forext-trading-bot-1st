# Receiver executable and configuration integrity

Classification: `RECEIVER_EXECUTABLE_INTEGRITY_UNVERIFIED` and `RECEIVER_CONFIGURATION_INTEGRITY_UNVERIFIED`.

No receiver program was installed. No service, task, or environment variable was changed.

G.14.11 required a different SID and did not say where the program bytes live. A different SID does not help if this user can replace the program, a DLL, or a Python module. The clause below closes that design gap. It is not a measured DACL.

## Placement

The receiver executable, the Python runtime it is allowed to load, its configuration file, and its audit log must sit on the ancestor chain in `filesystem_ancestor_trust_contract.md`. Owner is the receiver SID. The interactive SID has no write, delete, WRITE_DAC, or WRITE_OWNER on those files or on any ancestor.

The interactive user's PATH, PYTHONPATH, PYTHONHOME, user site-packages, and current working directory are not search paths. The process starts with a fixed environment allowlist and does not inherit the user environment. That allowlist must not contain broker tokens, database passwords, or Docker credentials. Those values were not read here.

DLL search is limited to the receiver tree. A writable current directory must not be used to resolve DLLs. Plugin directories, auto-update, and extra script loaders are out of the design. There is no Windows service and no scheduled task in the preferred R1 shape. Adding either is a new approval and a new binary-path test.

## Launch, stop, and logs

Launch authority is a starter that can create a process as the receiver SID. The starter binary is on the same chain. How that starter is invoked is not solved by this document. If the only person who can start it is this user after elevation, the medium-integrity user must still be unable to write the starter. That test does not exist.

Termination and restart rights for the interactive medium token must fail. Process DACLs were not read. Administrators are not claimed to be unable to terminate the process.

Logs and crash dumps stay in the receiver tree. They must not be written to the user profile, the repository, or a production mount. Audit files are created on the receiver handle. A crash dump that includes the environment is a defect because the environment must not hold secrets in the first place.

## What remains

No file was hashed as a receiver binary because none exists. No import path was locked. Implementation stays blocked. Using the Python that this user can already run is not acceptance of C03.
