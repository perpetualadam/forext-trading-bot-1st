# Packaging allowlist review

`ALLOWLIST_RECONSTRUCTION_UNVERIFIED` for the historical G.10 and G.14.1 packages as descriptions of the current tree.

The G.10 file lists 63 paths and records older hashes for `Dockerfile` and `app.py`. It cannot be treated as the current file set. The G.14.1 staging directory was not opened, so its 63-file inventory was not reconstructed from the directory.

The current Dockerfile is an explicit 61-file copy list. A static import walk from `forex_bot.app` and `main.py` did not find a required local module outside that list, and every copied path exists. That is a current-file observation, not a hash-sealed manifest.

The historical allowlist would omit the current source bytes because its recorded hashes differ. It would also describe an older Dockerfile. It does not, by itself, include `.env` or `/data`.

No allowlist was modified and no deployment package was produced.
