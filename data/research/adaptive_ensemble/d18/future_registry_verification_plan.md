# Future registry verification

This plan is not authorised.

Prerequisite: an explicit user selection of the OCI platform and confirmation of the registry. The Dockerfile does not name a registry hostname. A short name is not that confirmation. Architecture selection comes before any platform-specific digest request.

After that approval, a later stage may send a read-only manifest request to the approved registry endpoint for repository `python`, tag `3.12-slim-bookworm`, and the selected platform only. It records the index digest and the platform manifest digest separately, then the configuration digest if the manifest provides it. It checks those digests against the recorded bytes. It does not authenticate with broker or Telegram credentials. It does not pull the image, run Docker, start a container, or read production state.

Stop if the platform is still unspecified, the registry returns more than one platform and the selection is ambiguous, the digest cannot be recorded, or the request would pull blobs.

Python patch, Debian revision, and libc version may be absent from manifest labels. Those facts then need a separate isolated metadata inspection. They do not justify a production inspection.
