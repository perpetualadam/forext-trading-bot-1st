# Future registry verification

This design is not authorised.

A later stage may query one approved registry, read an OCI index or platform manifest, record the index digest and the selected platform's manifest digest separately, check media types and repository identity, and store the response under an approved output directory. It may not authenticate with trading credentials, download layers, pull an image, run Docker, or read production state.

Prerequisites that are not met now: an explicit OCI platform, an explicit registry, an explicit repository, an explicit tag or immutable reference, an approved network destination, approved read-only methods, a response-size limit, an output directory, a timeout, and a verification procedure.

Because the platform is unselected, registry verification is not authorised. Because the registry is unconfirmed, a presumed default registry must not be queried. The allowed destination remains unset.
