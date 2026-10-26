# Network guard review

The D.12 runtime used the D.11 network denials without weakening them. Guard self-checks passed. No external DNS, no broker HTTP, no Telegram HTTP, and no PostgreSQL connection were allowed. The final network list was empty in the contract, repeated-lifespan, and ownership children.
