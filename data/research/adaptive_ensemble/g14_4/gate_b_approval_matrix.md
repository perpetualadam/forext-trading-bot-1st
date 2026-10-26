# G.14.4 Gate B approval matrix

No row is granted.

| Action | Purpose | Network | Code execution | Writes | Destination | Allowed interface | Stop conditions | Granted |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Package-index metadata | Discover versions for the nine requirements and their graph | yes | no | notes only | `g14_4` evidence, no wheelhouse | a later approved index request | unapproved host, redirect, second index | no |
| Wheel-only resolution | Select linux/x86_64 CPython 3.12 wheels | yes | no install | a resolution record | evidence directory | resolver that cannot fall back to source | `COMPATIBLE_WHEEL_UNAVAILABLE` | no |
| Wheel downloads | Store selected `.whl` bytes | yes | no | wheel files | new empty temp directory | `pip download` template only after placeholders are resolved | nonempty dest, sdist, extra file | no |
| SHA-256 verification | Re-hash every file | no | no | a verification record | evidence directory | `tests/g14_4_verify.py` logic, independently | hash, size, or inventory mismatch | no |
| Wheel metadata parsing | Read `WHEEL` and `METADATA` inside the zip | no | no code execution | a metadata record | evidence directory | zip read of those two members only | executable entry, bad tag | no |
| Lockfile generation | Write the canonical lock | no | no | one lock file | evidence directory, not production requirements | schema `g14_4_lock_schema_v1` | missing hash, unknown toolchain | no |
| Independent lock verification | Second pass over the lock and files | no | no | a pass/fail record | evidence directory | a checker that does not import the downloader | any failed check | no |
| Candidate packaging | New Dockerfile and staging allowlist | no | no | new candidate files only | outside the 63-file context | a later packaging review | reuse of the old manifest digest | no |
| Docker metadata | Recheck image ID and tag | no | no | a metadata note | `g14_4` evidence | the G.14.2 read-only command list | identity mismatch | no |
| Docker image build | Build a candidate image | yes if pip remains | pip hooks if install runs | an image | local Docker | not requested | any of the above unfinished | no |
| Image export | Save the candidate for offline inspection | no | no | a new archive | a new temp path, not the G.12 archive | `docker image save` of that tag only | wrong tag | no |
| Runtime test | Start the candidate | no broker | application code | isolated test output | not production mounts | not requested | any trading path | no |
| Production deployment | Replace the running bot | no | production process | production | running container | not requested | always, until a later gate | no |
| Rollback | Restore an image | no | production process | production | running container | not requested | no verified rollback target | no |
