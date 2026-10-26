# Registry authentication

Public metadata, an anonymous bearer-token exchange, a logged-in registry session, and a credentialed pull are different.

The preferred future approach is an anonymous read of the index and the two platform manifests, if that registry allows it. This stage does not assume that anonymous access works.

No credential was read, stored, or requested. No token was created. No login was attempted.

If a future read receives an authentication challenge that anonymous access cannot satisfy, that stage stops and asks for a separate approval. A pull-scoped token is not authorised by the image-reference approval.
