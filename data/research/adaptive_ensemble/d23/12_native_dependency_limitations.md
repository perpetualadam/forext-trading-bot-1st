# Native dependency limitations

This record uses the current `requirements.txt` text and the D.17 native-wheel matrix. It does not resolve dependencies.

## Declared direct requirements

`requirements.txt` contains nine lower bounds and no hashes:

- python-dotenv>=1.0.0
- pandas>=2.0.0
- numpy>=1.24.0
- requests>=2.31.0
- psycopg2-binary>=2.9.9
- fastapi>=0.109.0
- uvicorn[standard]>=0.27.0
- oandapyV20>=0.7.2
- tzdata>=2024.1

`requirements-dev.txt` includes that file and adds packaging and pytest bounds. D.21 `22_dependency_boundary.md` records the same nine production lower bounds and the absence of a lock.

## Known native-dependency candidates

These candidates are not a complete transitive set:

- numpy, recorded by D.17 `native_wheel_risk_matrix.json` with wheel tag MISSING.
- pandas, recorded by the same matrix with wheel tag MISSING.
- psycopg2-binary, recorded by the same matrix as the intended binary distribution, with wheel tag MISSING.
- uvicorn[standard], declared with an extra. D.17 did not enumerate its transitive native components. Those components remain unknown.

## Per-platform unknowns

The same unknowns apply independently to linux/amd64 and linux/arm64 variant v8:

- Unknown Python ABI.
- Unknown wheel-tag compatibility.
- Unknown native shared-library requirements.
- Unknown package-artifact selection.
- Unknown transitive closure.
- Unknown exact dependency versions.

Dependency readiness remains UNVERIFIED for interpreter compatibility and MISSING for wheel tags, exact versions, and the transitive closure. No wheel was downloaded and no lock was generated.
