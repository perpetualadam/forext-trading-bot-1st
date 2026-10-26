# Windows procedure

This procedure runs only the safe offline command. Do not type an account identifier or a token. Do not run the future live command during Boundary B1.

1. Open the Start menu, type `Windows Terminal`, and open that app.
2. Go to the project folder `Forext Trading Bot 1st` on the Desktop under OneDrive.
3. Check the B1 executable:

   `python -B -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path(r'data/research/adaptive_ensemble/r55/b1/session_main.py').read_bytes()).hexdigest())"`

   The hash must be `af9a93edc6779298f819430062e34b48289fced922d65f24a1d62a0982be8a90`.
4. Check the files the session actually imports:

   `python -B -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path(r'data/research/adaptive_ensemble/r55/b1/transport.py').read_bytes()).hexdigest())"`

   That hash must be `3727df8494d6076a5997d88bd5be2a8fb4dc9a0a5f3428c65dc3f0e4002de20a`.

   `python -B -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path(r'data/research/adaptive_ensemble/r53/connector.py').read_bytes()).hexdigest())"`

   That hash must be `7e6bd27a3a65fec3e59e53771cd783c33e92d83b0ac7437a4d4caa0f37dc3df4`.

   `python -B -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path(r'data/research/adaptive_ensemble/r50/connector.py').read_bytes()).hexdigest())"`

   That hash must be `4520a39688001f4947d06a8c18dc0e404df7271c3ca79b0f62d64812fefab5f8`.

   `python -B -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path(r'data/research/adaptive_ensemble/r48/readonly_transport.py').read_bytes()).hexdigest())"`

   That hash must be `3ef1be4e565b7e2f783931e66e962ba3264f4be551bda2e4cd87f1705bf3b844`.

   `python -B -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path(r'data/research/adaptive_ensemble/r50/fixtures.py').read_bytes()).hexdigest())"`

   That hash must be `bf03349d425c27f36f989182a051460d4d7da2535937ccd70019fbb4647a42ee`.
5. These files are hash-checked and are not imported: R.51 `https_adapter.py` (`e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef`), R.52 `session_entry.py` (`59cb2fab00a0a1ea67c26261571498f623e8610a8e4e55ae64ac27a3a750ac56`), R.54 `session_main.py` (`50d2dfd2b3c7e2909994e7ccbebfd30d7c50021e8a2a8f70df5f11d78b880280`), and R.55 Boundary A `session_main.py` (`5913a190812343a9039570893f6cc96fb30fb2a08a6305b84e0bb7bea3576cf8`). If any hash differs, close the window.
6. Run the safe offline command:

   `python -B "data\research\adaptive_ensemble\r55\b1\session_main.py" --offline`

   A command with no arguments must instead print `R55 B1 default entry is disabled. No credential prompt. No network connection.`
7. Do not add any other argument. An unrecognised argument keeps the default disabled sentence. A live-only argument is rejected and prints `R55 B1 live entry is disabled. No credential prompt. No network connection.` It does not ask for credentials and it does not connect. Boundary B2 is still required before any real session can be considered.
8. The offline command prints this preview before its synthetic reads: host `api-fxtrade.oanda.com`, GET, instruments then pricing, the six pairs `EUR_USD`, `GBP_USD`, `AUD_USD`, `USD_CAD`, `USD_CHF`, and `USD_JPY`, maximum 2 requests, 5 seconds each, certificate verification enabled, redirects disabled, retries disabled, trading actions prohibited, broker token permissions UNKNOWN, account home currency not API-verified, and spread-bet stake semantics unverified. It does not show an account identifier, a token, an authorization header, or a full web address.
9. In a future approved run, continuation requires the exact local text `CONFIRM PREVIEW`. Any other answer stops the program.
10. Only after that confirmation would a future approved run ask for the account identifier and then the token with hidden input. Do not type either value now. The offline command uses built-in synthetic readers and does not ask.
11. To abort before a request, close the window. During a future prompt, press Ctrl+C or close the window before the confirmation is finished.
12. Once a request has been sent, closing the window does not retract that request.
13. The last lines of the offline command are the three counters and the evidence class. A successful synthetic run prints `2`, then `2`, then `2`, then `SYNTHETIC_TEST_ONLY`. Those three numbers are attempted requests, HTTP successes, and validated responses. Two attempted requests alone are not a success.
14. The synthetic file is `data\research\adaptive_ensemble\r55\b1\06_synthetic_output.json`. It is labelled `SYNTHETIC_TEST_ONLY`. It is not broker data.
15. You may send back the hash results, the disabled sentence, the three counts, and the evidence class. Do not send an account identifier, a token, a full web address, an authorization header, or a raw response.
