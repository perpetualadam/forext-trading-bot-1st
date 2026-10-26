# Request accounting

The counters are separate. They are recorded only after the preview is confirmed.

| Case | requests_attempted | successful_http_responses | validated_sanitised_responses | Stop |
| --- | ---: | ---: | ---: | --- |
| Confirmation refused | 0 | 0 | 0 | Before credentials and before any client. |
| Synthetic success | 2 | 2 | 2 | After pricing. Both connections closed. |
| HTTP 302 on the first response | 1 | 0 | 0 | `HTTP_ERROR`. Body not read. No pricing call. |
| HTTP 500 on the first response | 1 | 0 | 0 | No result file. |
| Timeout on the first request | 1 | 0 | 0 | `TIMEOUT`. No second call. |
| TLS failure on the first request | 1 | 0 | 0 | `TLS_FAILURE`. No second call. |
| Malformed JSON on the first body | 1 | 1 | 0 | `MALFORMED_JSON`. |
| Body over the size cap | 1 | 1 | 0 | `RESPONSE_TOO_LARGE`. |
| Unexpected instrument `NZD_USD` | 1 | 1 | 0 | `SCHEMA_REJECTED` before pricing. |
| Non-finite bid | 2 | 2 | 1 | Pricing rejected. `rows` empty. |
| Ask below bid | 2 | 2 | 1 | Pricing rejected. |
| Conversions absent | 2 | 2 | 2 | Factors recorded as `NOT_RETURNED`. |

Two attempted requests are not a successful session. The success file is written only for the 2 / 2 / 2 case. Offline evidence is `SYNTHETIC_TEST_ONLY`.
