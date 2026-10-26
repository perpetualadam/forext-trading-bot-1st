# G.14.3 candidate-image verification plan

Do not export or start an image in this stage. No candidate image exists.

A later inspection, after Permission F, would use image metadata, history, and a new archive outside OneDrive. It would not use `docker run`, `docker create`, `docker exec`, or `docker cp`. It would not recreate the deleted G.12 archive. It would not start FastAPI to read packaging.

1. Record the candidate image ID. The ID does not prove package source or integrity.
2. Compare the base layer with the intended identity. Today that identity is only the historical local image ID, not a registry digest.
3. Record image configuration, including working directory, command, exposed port, and user. Do not collect environment-variable values into the report.
4. Record image history. History does not prove exact dependency versions.
5. Record layer digests from the archive.
6. Read installed distributions from metadata in the image, not by running the application. If a distribution list is absent, record `UNKNOWN`.
7. Compare those versions with the future lock. There is no lock now.
8. Record dependency hashes only when the wheelhouse manifest supplies them. Do not reconstruct hashes that were never captured.
9. Check the 61 application files: 59 package files, `main.py`, and `requirements.txt`.
10. Reject any other application file.
11. Reject credentials and both backup filenames.
12. Reject research trees.
13. Reject operational-state files.
14. Confirm the entrypoint command remains `uvicorn forex_bot.app:app` on port 8000.
15. Confirm `WORKDIR /app`.
16. Confirm port 8000.
17. Record the runtime user. The current Dockerfile sets no `USER`, so the image default applies. Do not claim a non-root user was configured.
18. Record that the build, if it used the current Dockerfile, required network. An offline claim is allowed only after a wheelhouse build.
19. Record build provenance as `UNKNOWN` unless a later approved export contains it.
20. Recheck the candidate tag immediately before the build. If it exists, stop. Do not overwrite it.

Export size is unknown. Deletion of a future archive needs its own approval.
