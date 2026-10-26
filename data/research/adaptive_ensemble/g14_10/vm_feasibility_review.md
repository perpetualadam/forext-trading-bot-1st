# Disposable virtual machine feasibility

Classification: `VM_FEASIBILITY_PLAUSIBLE_UNVERIFIED`

Verified isolation: no. Feasibility of a secure disposable VM is not established. A running Hyper-V management service is not a guest.

## What was observed

Level 2, this stage, this machine:

- `Win32_ComputerSystem.HypervisorPresent` is true. The property does not name the hypervisor.
- `Win32_Processor.VirtualizationFirmwareEnabled` is true.
- The same WMI query returned false for SLAT and for VM monitor mode extensions. Those raw values are recorded. They are not treated as proof that SLAT is missing or that creation of a VM is blocked. No hypervisor command was run to corroborate them.
- Service `vmms` is present, running, and automatic.
- Services `vmcompute` and `hvhost` are present and running.
- `vmms.exe` and `vmcompute.exe` exist under `System32`.
- Default paths for VirtualBox `VBoxManage.exe` and VMware Workstation `vmware.exe` are absent. Other install locations were not searched.
- This process is medium integrity and not elevated.

Windows edition strings were read: ProductName `Windows 10 Pro`, EditionID `Professional`, DisplayVersion `25H2`, CurrentBuild `26200`. Licensing text was not read. Edition support for Hyper-V is not inferred beyond the fact that `vmms` is already running.

## What was not observed

No VM management command ran. There is no inventory of virtual machines, virtual switches, host-only networks, NAT networks, or bridged networks. Shared folders, clipboard, drag-and-drop, and guest tools are unknown. Snapshot support and destruction procedure are unknown. Memory and disk headroom are unknown. Whether this unelevated token can create a VM is unknown. Elevation was not requested.

## Trust anchor

The anchor would be a guest filesystem owned by a principal this user cannot reconfigure, with no shared folder. That anchor was not found. `HypervisorPresent` does not identify who can replace a virtual disk on the host. G.14.8 showed this user can replace a directory they can write. A VHDX on a user-writable path would be the same shape of problem. No disk path was inspected.

## Isolation claims that are not supported

- Guest filesystem isolation: unknown.
- Host filesystem exposure: unknown.
- Credential inheritance into a guest: unknown.
- Network egress control: unknown.
- Independence from the running production container: unknown. The historical Docker engine used a WSL2 kernel string. Whether that engine and Hyper-V share a host was not remeasured. They must not be assumed separate or assumed identical.

## Artifact export and import

No export method was available to inspect. A copy onto a normal Windows directory would end in `CreateFileW` on a path this user can replace. That is the G.14.8 finding, level 1, not re-run here. Host-side verification would have the same open. No receiving principal exists.

## Target compatibility

The host architecture is AMD64. That makes an x86_64 guest conceivable. It does not identify CPython patch, SOABI, glibc, pip, or wheel tags. The historical image id is not a registry digest. A VM was not started, so none of those values were read.

## Privileges and approvals

Creating a VM, changing a virtual switch, or attaching a disk was not attempted. This token is not elevated. A future creation stage would need its own approval, and it may need elevation. This stage does not grant either.

## Classification

`VM_FEASIBILITY_PLAUSIBLE_UNVERIFIED`

The management service is running, so the category is not `UNKNOWN` and not `BLOCKED`. It is not `SUPPORTED_BY_EXISTING_EVIDENCE` as an isolation architecture. No candidate VM is selected.
