# R.87F commit scope

Executed git add -- .github/workflows/ci.yml. Staged name list contained exactly that single path; staged diff --check succeeded; the staged diff matched the reviewed working diff. Created one commit with git commit -m "ci: add isolated offline exposure contract job".

Commit a8055c6a9f503a27a8f85d019473f67a3698c3c1; direct parent 9ba819cf1f08b92780a19df5f1d8e54df2c2134d. Exactly one changed file, 15 inserted lines. No operational/test/dependency/gate file, report, proposal or scheduler data staged. No previous commit amended.

Immediately before push, git fetch origin succeeded (exit 0). origin/main remained the verified parent; git merge-base --is-ancestor origin/main HEAD succeeded. Executed git push origin main successfully (exit 0), normal fast-forward. No protection rejection/bypass or repository-setting change.

Raw working workflow SHA-256: b37d32008e529f6cfc40a618aa9aba66f39dba4752cb975395ac8ddf322d42c2. Committed LF blob SHA-256: aafaa3c3eed3d92280da9b84f39822d3fb642b2729e1c67a243060846326a686. Existing text=auto/eol=crlf rules explain the CRLF working file versus LF Git index; no manual normalization occurred. The first strict staged-versus-working raw-byte equality check failed on this expected encoding distinction; an explicit byte/line-ending comparison established only Git's normal CRLF-to-LF conversion and an identical authorised diff. No source file was rewritten to satisfy the check.
