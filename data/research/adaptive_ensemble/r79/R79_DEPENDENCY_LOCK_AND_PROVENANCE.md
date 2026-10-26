# R.79 Dependency Lock and Provenance

Evidence class: review of `requirements.txt` and the pip install report at `$HOME/r79-pip-report.json` on the Linux host. The report is outside the repository and is not in the source archive.

`requirements.txt` declares minimum versions only:

- python-dotenv>=1.0.0
- pandas>=2.0.0
- numpy>=1.24.0
- requests>=2.31.0
- psycopg2-binary>=2.9.9
- fastapi>=0.109.0
- uvicorn[standard]>=0.27.0
- oandapyV20>=0.7.2
- tzdata>=2024.1

`requirements-dev.txt` was not installed. No repository setup script was executed. Packages came from PyPI as ordinary wheels, except `oandapyV20`, which was built from its source distribution by pip. That build is the package's own setup, not a repository entrypoint.

Resolved direct and transitive packages, with SHA-256:

| Package | Version | SHA-256 |
| --- | --- | --- |
| python-dotenv | 1.2.4 | `42269a8a5b3fd54ffa6f3d84b18abed50064717576b4ecf03dc4a55d8aa04fdc` |
| pandas | 3.1.0 | `9433b5dc2f26ef9d9b56daaf4d41d078bf4372c5d88c42ed5b397a6eea80de16` |
| numpy | 2.5.4 | `fbde6962867ee75b48b0ee29b2b9372ec5d617799dbaf38e82dc0596f2f7738a` |
| requests | 2.34.2 | `2a0d60c172f83ac6ab31e4554906c0f3b3588d37b5cb939b1c061f4907e278e0` |
| psycopg2-binary | 2.9.13 | `e3861eba31f8ea8663fd876166b032fd89179e42aa63764d6feb281f13f9eb60` |
| fastapi | 0.162.0 | `3785963de305dd09912426cb81f2d230fce98ab3521cdfe97265c8d14983128c` |
| uvicorn | 0.54.0 | `505bdb0f318731d45f1f712071fc781a8981f6847a31c902c9f5e652d4f67faf` |
| oandapyV20 | 0.7.2 | `5ca3990f824d0b16afd49d8e08f7403862d2b3c5a583470f777db7f76f04d073` |
| tzdata | 2026.5 | `b683bd1b6659ddcd810ff02ad09ba821d4bf1065072805063eb35c49617905ac` |
| annotated-doc | 0.0.5 | `117bac03a25ede5df5440e855b32d556049ca169ead221505badf432fed4b101` |
| certifi | 2026.10.23 | `e9b54de76e530bb6cf0ccd036787103acb58fd42ba930ea8bf948ddbaa2f61d1` |
| charset-normalizer | 3.5.2 | `3d31298449090ab8d47b7b1b2a555ff73cac7ed438a08b7ac160980c7ebed649` |

| Package | Version | SHA-256 |
| --- | --- | --- |
| click | 8.5.0 | `255bc9599cf7748b4b1a446ccc735421bd08a2ae529a8b88597d3de5664ee360` |
| h11 | 0.16.0 | `63cf8bbe7522de3bf65932fda1d9c2772064ffb3dae62d55932da54b31cb6c86` |
| httptools | 0.9.0 | `3e3201fe4d46e0d15d7ff9fafc94a605da9eb82d2c5b9837f0368acb325481f1` |
| idna | 3.20 | `ab7ae7122974553370f0bdb919e1a960b2cd1bc1ef0276416d896db81c14582c` |
| opentelemetry-api | 1.45.1 | `b31553efa588ae44bc306f863c785c5333a9ecc091248c6ee68b4b6c87fdedfb` |
| pydantic | 2.14.1 | `9195d967ec791692a04438115466764fb8b9a27b31f14a760437694f40d6b454` |
| pydantic_core | 2.50.1 | `93ba4e9d8210d941c200431a56b2c0400b131865947903937ed3ec5404307d2e` |
| python-dateutil | 3.0.0 | `3c79630202e4152c6add678446984236efe4f57e84d8e892aab0637bab82e9fd` |
| PyYAML | 6.0.3 | `ba1cc08a7ccde2d2ec775841541641e4548226580ab850948cbfda66a1befcdc` |
| starlette | 1.10.0 | `478c0ab3b4ced6e82719849c118fa406f0278a3499c1a898cd15cd31bdc38ce4` |
| typing_extensions | 4.16.0 | `481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8` |
| typing-inspection | 0.4.4 | `65b8397ba37ccbce054456aaccddfc91e6e3083c92824df348d96ca832f3f147` |
| urllib3 | 2.8.0 | `0cf3cae568d36aa9576b28dfb35f11328f1cb974ca7647d9475ebb86c75ac6e3` |
| uvloop | 0.23.0 | `090865d8ce7a03986755a3ce711b7dd0d4b44eb14ab74368b717f3fad1180208` |
| watchfiles | 1.3.0 | `b5768b49e426fd5b550b012c866db347cdf15c398ef98dc557b6e6b72fa74cd1` |
| websockets | 17.3 | `a7f391838e8adcf1f2fe71561d9e5a9f74ea7ffa5052eb2db329aac677383136` |
| annotated-types | 0.8.0 | `f072f4d804ea359e4eaf198b1af7a8b0943881a87f31bb764f8bf219bb9419e0` |
| anyio | 4.15.1 | `6152fdbbf9a77fdec97731721bebf7c4c44f7c29b424b0065826173efc7ed101` |
| six | 1.17.0 | `4721f391ed90541fddacab5acf947aa0d3dc7d27b2e1e8eda2be8970586c3274` |

Install count: 31. No unexpected broker or credential package was present. `opentelemetry-api` is a FastAPI/Starlette transitive dependency. It was not used to export telemetry during the tests.

Reproducibility is partial. The report pins this install. `requirements.txt` does not, so a later resolver can select different wheels. No application code was changed by the install.
