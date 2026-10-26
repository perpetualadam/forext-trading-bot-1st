# Dependency security review

No vulnerability service was queried. Current dependencies are not claimed to be free of known vulnerabilities.

Future controls have to cover dependency confusion, typosquatting, substitution of an artifact that still satisfies a lower bound, hash mismatch, graph changes, yanked releases, native binary provenance, build-script execution, and compromise of the resolver, the index, or the artifact store.

The present install path has none of those controls. `pip install --upgrade pip` followed by an unhashed requirements install can select different bytes on a later build. Hash enforcement is the minimum control before any later install. A vulnerability review is a separate approval after versions are exact, not before.
