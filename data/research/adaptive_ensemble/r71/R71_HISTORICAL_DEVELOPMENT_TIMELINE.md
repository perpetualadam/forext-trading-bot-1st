# R.71 Historical Development Timeline

## Evidence classes

- Confirmed historical implementation: a commit that touches the file, or the current function body.
- Confirmed current behaviour: the working-tree source cited by line.
- Missing historical evidence: the original Trailing Stop Strategy chat, and any design that was never written into this tree.
- Inference: a filename or comment. Inferences are labelled below and are not treated as requirements.

## What git actually contains

This branch has 43 commits. The root is `ec68e8eced131276675f26c93f55d4e84a009abc`. The earliest messages are macro and research probes, not the birth of the bot. The operational modules are older than that visible story: many of them are already present at the root, and the working tree is dirty relative to HEAD (`bot_loop.py` is modified). A commit message is not used here as proof that a feature still behaves as the message says.

## Timeline that can be confirmed

| When | Evidence | What it supports |
| --- | --- | --- |
| Before the 43-commit history | Working tree contains sizing, OANDA client, strategies, and positions | The bot predates the recorded research commits. The original chat was not recovered |
| `526dda1` | `git log -- forex_bot/profit_protection.py` | Commit subject: add MFE profit protection, close diagnostics, and SSL reconcile retries. This is the earliest git evidence of the protection module |
| `a8e043c` | Same file history | Six-pair `FOREX_SYMBOLS` universe without raising portfolio caps |
| `ae1f878` | Same file history | Stop one-minute closes from stale M5/MFE. Current `live_manage.py` refuses to fall back to an M5 close for broker quotes |
| `e451920` | Commit subject only | Book broker-side SL/TP closes and pin entry SL/TP to the fill. Current `broker_sl_tp_hit` still returns false, so this subject is not current hit detection |
| R.66 | Audit reports | Findings R66-03, R66-05, R66-07, R66-10, R66-11 remain open in the current source |
| R.67A/B | Design documents | Ownership, protection, and close-state contracts. Not an operational state machine |
| R.68 | `positions.py` hash still the R.68 digest | Observation-only management boundary |
| R.70 | `reconciliation.py` hash is the R.70 digest | Incomplete OpenPositions bodies fail closed |
| R.56–R.65 | Research tree | Process containment. Not imported by `run_bot` |

## Requirements recovered from source, not from the missing chat

These are current defaults and docstrings. They match the numbers the user asked this audit to check. They are not a transcript of the original conversation.

- Activation fraction defaults to 0.67 of the position's stored take-profit distance (`profit_protection.py` lines 36–38).
- Giveback multiplier defaults to 0.5 and the ATR period defaults to 14 (lines 41–49).
- Fallback giveback defaults to 4 pips when ATR is missing (lines 52–54).
- The module docstring says the layer does not move broker or local stop or take-profit (line 1).
- `tests/test_profit_protection.py` describes the same behaviour. It was not executed, because pytest would load `tests/conftest.py`.

## Not recovered

- The original conversation text.
- A separate historical trailing-stop formula that amends an OANDA stop.
- A breakeven specification with a buffer.
- A partial-close specification with remaining-unit rules.
- Proof that every deployed account is GBP. The code has a currency field and also USD heuristics.
