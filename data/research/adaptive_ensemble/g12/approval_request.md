# Image-forensics approval request

Status: pending. The real image filesystem has not been read.

1. Exact image ID: `sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25`
2. Exact proposed command: `docker image save --output "C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st\data\research\adaptive_ensemble\g12\forensics\image_save.tar" sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25`
3. Docker daemon contact: yes, for that save only. The following hash and whiteout merge is local Python and does not call Docker.
4. Writes files: yes. One save tar, then a redacted hash report.
5. Storage: reserve 250 MB. The stored image size is 111,899,777 bytes. The full unpacked root, previously listed near 483 MB, will not be materialised.
6. Output directory: `data/research/adaptive_ensemble/g12/forensics/`
7. Credentials: container environment values are not in the save. A copied env file inside a layer would be reported by path only.
8. Deleted historical files: a whiteout hides a path in the merged filesystem and leaves the earlier blob intact. Those paths will be listed without contents.
9. Running containers: not modified. The save does not start, stop, or replace `forexttradingbot1st-bot-1`.
10. Protection: reports store hashes and names. Secret values are not written. The export stays under `data/` and outside the G.10 snapshot.
11. Temporary files: `image_save.tar` is deleted after the hash report. The redacted report remains.
12. Without this operation: the image ID, tag, creation time, and `COPY` history lines are known. File bytes, provenance, and the management repair are not.

No other command is requested. `docker create`, `docker run`, `docker exec`, and `docker cp` are not part of this request.
