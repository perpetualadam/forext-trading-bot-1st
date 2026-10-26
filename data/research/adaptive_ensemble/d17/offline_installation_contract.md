# Offline installation contract

A future installation is accepted only if it uses the lock as the only version source, verifies every hash, installs only those artifacts, and has no network and no index. It must not build from source, upgrade anything, or write outside a disposable environment.

It must not use the production bot environment, the production database, broker credentials, or Telegram. This stage did not run that installation.
