# Prepared HTTPS factory

`open_prepared_connection` builds a default TLS context and requires certificate verification plus hostname checking. It then constructs one object with:

- Host `api-fxtrade.oanda.com`
- Port `443`
- Timeout `5.0` seconds
- The verified context
- No proxy argument, no tunnel, and no extra keyword

`HTTPS_PROXY` and `HTTP_PROXY` were set in the test process. The constructed object still received the fixed host and port 443.

The real `http.client.HTTPSConnection` class, and any subclass of it, is refused before construction. `read_bounded` also refuses a live client object. A non-200 status raises `R52_REJECTED` without reading the body and without placing the body in the exception. A body above 1,048,576 bytes is refused. Malformed JSON raises the same fixed code.

`launch` does not call this factory. The synthetic session uses an injected factory through the R.51 adapter, not this live class.
