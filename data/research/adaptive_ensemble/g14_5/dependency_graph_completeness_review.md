# Dependency graph completeness

Nine direct requirements are known. None has an exact pin or a hash. The transitive set, including packages introduced by `uvicorn[standard]`, is unknown.

The inventory helper does not retain environment markers. The verifier checks only the names listed in the manifest `requires` field. A matching hash does not prove that every `Requires-Dist` edge is present.

Classification: `DEPENDENCY_GRAPH_COMPLETENESS_UNVERIFIED`.

No complete lock and no real wheelhouse were created.
