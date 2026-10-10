# Stage G.12 readiness

Classification: `IMAGE_FORENSICS_APPROVAL_REQUIRED`

The running image ID is unchanged: `sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25`. Its filesystem has not been read. Rollback remains `ROLLBACK_CANDIDATE_UNVERIFIED`.

Git HEAD does not contain `live_safety.py` or `market_provenance.py`. The G.7 and G.10 archives do. Those archives differ in `bot_loop.py`, `oanda_exec.py`, and `decision_skip_log.py`. None of those facts identifies the bytes inside the image.
