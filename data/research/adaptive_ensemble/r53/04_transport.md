# HTTPS transport

`transmit` builds a certificate-verified TLS context and constructs one injected client with host `api-fxtrade.oanda.com`, port 443, and a five-second timeout. It sends one GET, with no body and no stream. Status other than 200 raises `HTTP_ERROR` without reading the body. A body above 1,048,576 bytes raises `RESPONSE_TOO_LARGE`. Malformed JSON raises `MALFORMED_JSON`. `TimeoutError` raises `TIMEOUT`. `ssl.SSLError` raises `TLS_FAILURE`. None of these are retried, and none of their text is copied into the result.

The real `http.client.HTTPSConnection` class, and any subclass, is refused before construction. `launch` does not call `transmit`. Proxy variables do not change the host or port. The exception text remains `R53_REJECTED`.
