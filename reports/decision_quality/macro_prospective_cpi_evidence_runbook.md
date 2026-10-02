# CPI T−48h operator runbook

Event: `usd_cpi_2026-10-14`
T0: `2026-10-14T12:30:00Z`
T−48h: `2026-10-12T12:30:00Z`

Consensus provider: **NONE_APPROVED**
Provider status: **PROVIDER_PENDING**
Automated collection: **DISABLED**
Manual collection: **WAITING_FOR_APPROVED_PROVIDER**

Trading Economics is operationally retired. Do not open, refresh, capture, or transcribe TE Consensus or TE Forecast for upcoming CPI checkpoints.

No automated website access. No OCR. No Trading Economics / Forex Factory / BLS request.

Expected consensus series already defined by the prospective schema:

- `headline_mom`
- `headline_yoy`
- `core_mom`
- `core_yoy`

A proprietary provider forecast is not automatically a consensus. A model forecast is not a consensus. A nowcast is not a consensus. A single economist forecast is not automatically a market consensus. Never substitute Forecast for Consensus. A blank Consensus stays missing, not zero. Never copy forward an earlier value.

## Before first checkpoint

1. Confirm an approved consensus provider exists.
2. Confirm its exact consensus semantics (survey / poll / median / mean or equivalent aggregated expectation).
3. Confirm the permitted access method. Do not bypass access restrictions.
4. Record the provider ID.
5. Confirm the four CPI components are available.

If no approved provider exists: do not manufacture an observation.

## At each checkpoint

1. Access the approved provider using the permitted method.
2. Capture the source manually if manual collection is approved.
3. Save the original artifact locally as `.png`, `.jpg`, `.jpeg`, or `.mp4`.
4. Immediately archive the exact local file:

```
python -m reports.decision_quality.macro_prospective_cli evidence-intake --event-id usd_cpi_2026-10-14 --checkpoint T48H --file "C:\path\to\capture.png" --provider-id <approved-provider>
```

Use `T36H`, `T24H`, `T12H`, `T6H`, `T4H`, `T2H`, `T1H`, `T30M`, `T15M`, or `T5M` for later vintages.

5. Confirm the receipt starts with `MANUAL EVIDENCE SECURED`.
6. Confirm `SOURCE_SHA256` equals `ARCHIVED_SHA256`.
7. Confirm `OBSERVATION_ELIGIBLE` is `YES` before transcribing values.
8. Only then type the displayed values into a JSON file. Example:

```json
{
  "headline_mom": {"consensus_raw": "0.2", "forecast_raw": "0.2", "previous_raw": "0.1"},
  "headline_yoy": {"consensus_raw": "3.1", "forecast_raw": "3.0", "previous_raw": "2.9"},
  "core_mom": {"consensus_raw": "0.2", "forecast_raw": "0.2", "previous_raw": "0.2"},
  "core_yoy": {"consensus_raw": "3.0", "forecast_raw": "3.1", "previous_raw": "3.0"}
}
```

9. Ingest values against the secured evidence ID from the receipt. Provider identity is required and is never assumed to be Trading Economics:

```
python -m reports.decision_quality.macro_prospective_cli evidence-ingest-values --event-id usd_cpi_2026-10-14 --checkpoint T48H --evidence-id "<EVIDENCE_ID>" --provider-id <approved-provider> --components-json values.json
```

10. Run `python -m reports.decision_quality.macro_prospective_cli status`.
11. Confirm exactly one observation for that checkpoint.

Optional inspect-only pass:

```
python -m reports.decision_quality.macro_prospective_cli evidence-intake --event-id usd_cpi_2026-10-14 --checkpoint T48H --file "C:\path\to\capture.png" --provider-id <approved-provider> --dry-run
```

## If no approved provider exists

Do not manufacture an observation.
Do not create `Consensus = null` merely to mark a checkpoint collected.
The scheduler may still evaluate checkpoint timing and record `NO_ENABLED_SOURCE`.
A due checkpoint with no genuine evidence becomes `MISSED_NOT_OBSERVED` under existing rules.
