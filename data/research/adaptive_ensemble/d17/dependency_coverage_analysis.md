# Dependency coverage

The 60 Python files named by the Dockerfile were parsed with `ast`. None failed to parse. No `__import__` or `importlib.import_module` call was found in that set.

Third-party import roots were `dotenv`, `fastapi`, `numpy`, `oandapyV20`, `pandas`, `psycopg2`, `requests`, and `uvicorn`. Each has a corresponding production requirement. `psycopg2` is the import name and `psycopg2-binary` is the declared distribution. Installed package metadata was not queried, so that mapping is a naming inference from the two local texts.

`zoneinfo` is imported from `forex_bot/session_rules.py`. It is in the standard library. `tzdata` is declared and is not imported by name. Whether the slim image contains system timezone data, and whether the pip `tzdata` package is what `zoneinfo` loads, was not verified.

`pytest` appears in top-level tests and is declared only in `requirements-dev.txt`. `packaging` is declared there and was not found by a tests import search. It was not removed. Its runtime role is unverified.

No third-party import in the image copy set lacked a production declaration. The scan used the host Python 3.13 standard-library name list. It did not walk the research tree. Optional entry points inside installed packages were not visible to static import scanning.

The Dockerfile copies `requirements.txt` and installs that file. It does not install `requirements-dev.txt`.
