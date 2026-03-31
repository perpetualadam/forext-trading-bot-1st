OHLCV CSV for backtests (no OANDA)

Format: header row with columns time, open, high, low, close (case-insensitive).
Times: UTC (ISO-8601 recommended). Each regime in the backtest keeps rows whose time falls in that regime window.

See eurusd_m5_2024_sample.csv for a short synthetic sample (covers only part of 2024; expand or replace with your own export).

Export sources: Dukascopy, HistData, broker exports, etc. — resample to your bar size and align with REGIME_PERIODS in forex_bot/backtest.py.
