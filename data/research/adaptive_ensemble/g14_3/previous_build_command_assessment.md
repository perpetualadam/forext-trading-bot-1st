# G.14.3 previous build command

The command was not executed.

```text
docker build --pull=false --progress=plain -f "C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2\Dockerfile" -t forexttradingbot1st-g14-candidate:d080d89-4a458b4b "C:\Users\Brian\AppData\Local\Temp\forext-g14-1-staging-0yifygx2"
```

| Question | Assessment |
| --- | --- |
| Context path | The verified 63-file staging directory. Not the repository root. |
| Candidate tag | `forexttradingbot1st-g14-candidate:d080d89-4a458b4b`. Available at G.14.2 only. Not reserved. |
| Base image | Mutable tag. Local ID was recorded then. Registry digest unknown. |
| Pull | `--pull=false` does not stop a pull if the tag is missing, and it does not stop pip. |
| Network | Required for the unpinned pip upgrade and install. |
| Dependencies | Not reproducible. No pins, hashes, or wheelhouse. |
| Cache | Default cache may reuse an older resolution. |
| Third-party code | pip may run installation hooks. |
| Layer provenance | Not available until a build exists. BuildKit provenance is unverified. |
| Running production | The tag is not the running image. The command still must not be run under this stage. |
| Tag collision | Must be rechecked immediately before any future build. |
| Post-build checks | Defined in the verification plan. Not a substitute for a lock. |

## Recommendation

`REPLACE_WITH_LOCKED_OFFLINE_BUILD_PROPOSAL`

The staged context can stay. The command itself must not be approved as a reproducible build.

## Replacement status

- Executable with current evidence: none. A locked offline command would need a wheelhouse path and hashes, which are `UNKNOWN`.
- Requiring additional artifacts: exact versions, transitive inventory, wheel filenames, SHA-256 hashes, and a candidate Dockerfile.
- Requiring new approvals: Permissions B, C, and D before any such command can be written honestly. Permission E remains separate and is not requested.
