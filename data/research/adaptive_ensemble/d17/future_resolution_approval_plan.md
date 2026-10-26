# Future resolution approval

This stage is not approved now.

Inputs are the recorded `requirements.txt` hash and a completed target profile. The resolver name and version are pinned. The index is an approved host, not a general network grant. Allowed outputs are a lock file and a provenance template under a research or quarantine path. Every selected artifact must have a hash. The closure must be checked against markers for that one target.

The stage must not download a wheelhouse, install packages, open Docker, read secrets, contact OANDA or Telegram, or touch production state. A time limit and an index allow-list are part of the approval. If any selected distribution lacks a compatible wheel, the stage stops without promoting a lock.
