# R.78 dependency audit

No virtual environment was present. Nothing was installed. The WSL system interpreter is not a production environment, and it was used only for synthetic tests and import probes.

| Module | WSL status |
| --- | --- |
| `oandapyV20` | `ModuleNotFoundError` |
| `pandas` | `ModuleNotFoundError` |
| `numpy` | `ModuleNotFoundError` |
| `psycopg2` | `ModuleNotFoundError` |
| `dotenv` | `ModuleNotFoundError` |
| `requests` | present |

`oandapyV20` is the first blocker for `forex_bot.oanda_client`. It is not the only blocker. `forex_bot.bot_loop` fails first on `numpy` even after the OANDA import failure is known. `pandas` and `psycopg2` are also required by the repository manifest and are absent.

The existing manifest is `requirements.txt`:

- `python-dotenv>=1.0.0`
- `pandas>=2.0.0`
- `numpy>=1.24.0`
- `requests>=2.31.0`
- `psycopg2-binary>=2.9.9`
- `fastapi>=0.109.0`
- `uvicorn[standard]>=0.27.0`
- `oandapyV20>=0.7.2`
- `tzdata>=2024.1`

A disposable environment, if later authorised, would be a new virtualenv outside the repository and outside the production interpreter, installed from that manifest, used only with the R.69 isolation harness and temporary SQLite. That install was not performed.

Missing modules were not mocked. Import results below distinguish a real import from a missing dependency. A missing dependency is not a passing operational import.
