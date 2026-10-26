# Dependency graph validation

After archive inspection, `assert_dependency_graph` reads `Requires-Dist`, `Requires-Python`, and `Provides-Extra` from wheel metadata. Markers are evaluated for CPython 3.12 on Linux x86_64. The Windows host platform is not used. A marker that needs the Python patch version, SOABI, or glibc stays unknown, and the set is rejected.

A missing edge, unsatisfied specifier, or missing requested extra fails the acceptance path. `accept_verified_lock` still refuses the set because provenance is not approved. The production transitive graph remains `DEPENDENCY_GRAPH_COMPLETENESS_UNVERIFIED` because no real wheels exist. A consistent synthetic set is not a production lock.
