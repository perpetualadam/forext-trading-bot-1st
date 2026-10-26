# Request accounting

The counters come from the pinned R.53 connector, through `run_session`. They are stored separately.

| Case | requests_attempted | successful_http_responses | validated_sanitised_responses | Stop |
| --- | ---: | ---: | ---: | --- |
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

Two attempted requests are not enough to call the session successful. The success file was written only for the 2 / 2 / 2 case. Its evidence class is `SYNTHETIC_TEST_ONLY`.
