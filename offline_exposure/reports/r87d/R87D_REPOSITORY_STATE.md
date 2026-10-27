# R.87D repository state

Root/cwd: `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st`. Branch `main`; starting HEAD and fetched origin/main `883752f91510f639d354f090331446dcc6ade0a8`. Origin is https://github.com/perpetualadam/forext-trading-bot-1st.git; GitHub confirms default main, no branch protection, and no repository rulesets. One registered worktree, this root; no local work branch. An agent checkpoint namespace is present but is not a work branch.

Local `529277b837e15c2bda964e2a258e4c6badc121d3` is the immediate parent of main and contains the wrapper, as do 3495fe5 and inspected agent checkpoint blobs. Git object bot_loop hashes at those commits are all `2f1c36dc025d114685e4424402f6866c66aa6eb37d28717027c502a4f447118d`. The wrapper predates both reported HEADs. Their intervening commit does not alter operational code. No evidence in these trees of a later reintroduction following a committed sealed restoration.

The reported R.87B restoration is not in accessible committed trees. The cloud work branch/filesystem is unavailable; its physical repository/worktree cannot be identified here. The earlier handover explicitly says cloud edits were uncommitted/unpushed and the patch was not transferred. Evidence is consistent with a cloud-only uncommitted restoration at the older reference HEAD, not a lost committed correction. This is a finding about accessible evidence, not proof about every external checkout.

Starting staged diff empty. Two existing scheduler modifications remain: audit.jsonl and state.json under data/research/macro/consensus_pit/prospective/scheduler; contents were not read. Existing untracked proposal, pure exposure module and offline_exposure directory remain. All four candidate files are untracked, absent from main; no duplicate tracked patch exists there. Ignore rules exclude credentials, permits, consumed markers, caches and specified archive exports. No unrelated work reset, cleaned, stashed, reverted or overwritten.

Read-only discovery used git rev-parse --show-toplevel, git branch --show-current, git rev-parse HEAD, git status --short, git remote -v, git worktree list, git branch -avv, git for-each-ref, commit ancestry checks and path-restricted Git source reads. git fetch origin initially failed on sandbox FETCH_HEAD permissions; an approved escalated retry succeeded without moving HEAD or changing working files.

All four available refs/agents and refs/codex source snapshots were also inspected by bot_loop path only; each retains the same wrapper hash. Final main HEAD and origin/main advanced only through the one reviewed R.87D commit; see R87D_GITHUB_MAIN_STATUS.md.

Final GitHub branch collection independently lists only main and cursor/telegram-bot-commands-bae3; no remote work branch exists in that returned collection. main points to 9ba819cf1f08b92780a19df5f1d8e54df2c2134d. Final local HEAD and origin/main match it; staged diff remains empty.
