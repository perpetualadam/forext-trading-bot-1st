# R.43 future acquisition architecture

This design is not implemented. R.43 contains no client, no request function, and no script that can connect to OANDA or place an order. A later stage must be explicitly authorised before any of this is coded or run.

## Boundary

- Instruments: an explicit list in the later authorisation. The default candidate list is the existing six names. Shortlist names stay excluded until their own authorisation.
- Time range: an explicit UTC start and end. The exposed year `2025-09-01` through `2026-08-31` is not re-downloaded as if it were new.
- Permission: read-only market candles. Account-order and trade endpoints stay out of the client. If the token cannot be restricted, the client still must not call order or trade paths, and the run stops if a response is not a candle document.
- Environment: one named environment in the authorisation. Practice and live are not mixed in one manifest.
- Credentials: supplied by the later operator through the existing secret mechanism. This stage does not read them. Logs must not print them.
- Isolation: a research process only. It does not import `bot_loop`, start the scheduler, open PostgreSQL, or write `data/ops`.

## Transfer rules

- Throttle: at least one second between requests, matching the G.3 plan's minimum, unless the later authorisation sets a slower floor.
- Pagination: windows no larger than the documented candle-count limit. G.3 used seven-day windows and a documented cap of 5000 candles.
- Retries: at most two retries on a timeout or a rate-limit response. A 4xx contract error stops that instrument.
- Rate limits: honour the stated wait. Do not tighten the loop after a success.
- Clock: store provider timestamps as UTC. Do not convert with a local timezone.
- Prices: keep bid and ask OHLC. Do not replace them with a midpoint.
- Completeness: keep the provider complete flag. An incomplete boundary candle stays incomplete.
- Gaps: record intervals longer than one bar. Do not interpolate.
- Duplicates: reject a second row with the same instrument and timestamp.
- Metadata: instrument, granularity, price components, window, environment name, and retrieval time.

## Storage

- Raw responses are immutable. A later normalisation writes a new file.
- Each raw file and each normalised file gets a SHA-256.
- A provenance manifest lists hashes, windows, row counts, gap counts, and the authorisation identifier.
- Transformations are a separate script from the download. The same raw hash must reproduce the same normalised hash.
- Development rows and protected-holdout rows are partitioned before any feature script reads them. The holdout directory is not an input to development code.
- Restart is idempotent: a completed window with a matching hash is not requested again. A partial window is requested again and replaces only its own partial file.
- Failures log the instrument, window, status, and error class. They omit tokens, account identifiers, and response bodies that contain them.
- The process does not start a strategy evaluation when the download finishes.

## Stop

The later stage stops after the manifest and the quality report. It does not train a model, rank a strategy, or place an order.
