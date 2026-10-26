# Remaining risks

- The live connection factory is not implemented. This stage cannot verify the account, the host, or the token.
- Broker-enforced read-only permission is `UNKNOWN`. A later GET session would not prove the token cannot trade.
- Account home currency from these two responses is `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED`. The R.46 GBP screen stays separate evidence.
- The spread-bet stake map, the unrounded GBP pip value, and the margin class remain unknown. No executable size is calculated.
- Hidden input, even in a future Start-menu window, does not protect against a compromised terminal, a debugger, process-memory inspection, or an automated tool.
- A hand-written factory passed into `run_offline` could perform work. Launch does not pass one, and the real HTTPS class is refused. Review of any later factory is a separate authorisation.
- Synthetic prices in `06_synthetic_session.json` are fixtures. They are not OANDA spreads and they are not strategy inputs.
