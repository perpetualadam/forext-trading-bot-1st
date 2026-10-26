# Baseline and integrity

Inspection was read-only except for creating this preparation directory. No B1 file, earlier-stage source, production file, or Git history was modified.

Recorded before these documents were added:

- Branch: `main`
- HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Dirty working tree: yes, 256 porcelain entries. That dirt was left in place.
- The preparation directory did not exist before this task.

## B1 executable hashes

| File | SHA-256 | Result |
| --- | --- | --- |
| `data/research/adaptive_ensemble/r55/b1/session_main.py` | `af9a93edc6779298f819430062e34b48289fced922d65f24a1d62a0982be8a90` | Match |
| `data/research/adaptive_ensemble/r55/b1/transport.py` | `3727df8494d6076a5997d88bd5be2a8fb4dc9a0a5f3428c65dc3f0e4002de20a` | Match |
| `data/research/adaptive_ensemble/r55/b1/test_session.py` | `5f1998d22aee2510014fa831a6eb3f94f0af67ebbcfe7483ce0be523525b6b6d` | Match |
| `data/research/adaptive_ensemble/r55/b1/R55_B1_OFFLINE_VERIFICATION.zip` | `47c9fc740df9f037808221d8f60b3e44edbd45c8daabd649ad50f1c0db5d2a82` | Match |

## Dependency pins

| Pin | SHA-256 | Result |
| --- | --- | --- |
| `r51/https_adapter.py` | `e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef` | Match |
| `r52/session_entry.py` | `59cb2fab00a0a1ea67c26261571498f623e8610a8e4e55ae64ac27a3a750ac56` | Match |
| `r53/connector.py` | `7e6bd27a3a65fec3e59e53771cd783c33e92d83b0ac7437a4d4caa0f37dc3df4` | Match |
| `r54/session_main.py` | `50d2dfd2b3c7e2909994e7ccbebfd30d7c50021e8a2a8f70df5f11d78b880280` | Match |
| `r55/session_main.py` | `5913a190812343a9039570893f6cc96fb30fb2a08a6305b84e0bb7bea3576cf8` | Match |
| `r48/readonly_transport.py` | `3ef1be4e565b7e2f783931e66e962ba3264f4be551bda2e4cd87f1705bf3b844` | Match |
| `r50/connector.py` | `4520a39688001f4947d06a8c18dc0e404df7271c3ca79b0f62d64812fefab5f8` | Match |
| `r50/fixtures.py` | `bf03349d425c27f36f989182a051460d4d7da2535937ccd70019fbb4647a42ee` | Match |

No discrepancy was found. Nothing was repinned.

## Live disable, from source inspection

`launch` with `["--live"]` prints `R55 B1 live entry is disabled. No credential prompt. No network connection.` and returns 2. It does not call `run_live`.

`run_live` raises `R55B1_LIVE_NOT_SELECTED` as its only action.

`run_session` raises that code when `mode` is not `offline`, before callbacks. On the offline path it accepts only the exact built-in `SyntheticTransport`.

`run_test_session` is not referenced by `launch` or `run_offline`. Its docstring states that accepting a stand-in does not show the stand-in is free of network access, and that the test fixture is not a sandbox.

R.48 `perform_request` raises `R48_AUTHENTICATED_EXECUTION_BLOCKED`.

## Inspection scope

Read locally: `r55/b1/`, and the pinned R.48, R.50, R.51, R.52, R.53, R.54, and R.55 Boundary A files and notes that define the two GET routes, the sanitised fields, and the unresolved account facts. R.45 public-document notes were used only for the already recorded limits on conversion and financing. No external document was fetched.

This preparation imports no production module. The new files are Markdown. They do not import `forex_bot.config` or `forex_bot.oanda_client`.

## Discrepancies

None in the required hashes. The pre-existing dirty tree, including earlier `forex_bot` modifications, was not part of this task and was not edited.
