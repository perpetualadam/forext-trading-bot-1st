"""Account-summary diagnostics from an already-supplied document.

Home currency is copied only from a currency field. It is never inferred.
"""

from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
HOME_CURRENCY_UNVERIFIED = "ACCOUNT_HOME_CURRENCY_API_UNVERIFIED"
NOT_RETURNED = "NOT_RETURNED"
UNVERIFIED = "UNVERIFIED"
BROKER_REPORTED = "BROKER_REPORTED"


def _adapter() -> Any:
    name = "r56p2_response_adapter"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, HERE / "response_adapter.py")
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def build(document: Any) -> tuple[dict[str, Any], set[str]]:
    adapter = _adapter()
    account, warnings, secrets = adapter.account_view(document)
    if account is None:
        code = "EMPTY_RESPONSE" if "empty_response" in warnings else "REJECTED_DOCUMENT"
        return _rejected(code, warnings), secrets
    warnings = list(warnings)
    missing: list[str] = []

    raw_currency = account.get("currency") if "currency" in account else None
    if raw_currency is None or (isinstance(raw_currency, str) and not raw_currency.strip()):
        currency = HOME_CURRENCY_UNVERIFIED
        currency_source = UNVERIFIED
        is_gbp: bool | str = UNVERIFIED
        missing.append(HOME_CURRENCY_UNVERIFIED)
        warnings.append("missing_currency")
    elif adapter.currency_code(raw_currency) is None:
        currency = HOME_CURRENCY_UNVERIFIED
        currency_source = UNVERIFIED
        is_gbp = UNVERIFIED
        missing.append(HOME_CURRENCY_UNVERIFIED)
        warnings.append("incorrect_type")
    else:
        currency = adapter.currency_code(raw_currency)
        currency_source = BROKER_REPORTED
        is_gbp = currency == "GBP"

    balance, balance_source, balance_warnings = _money(adapter, account, "balance", "missing_balance")
    nav, nav_source, nav_warnings = _money(adapter, account, "NAV", "missing_nav")
    margin, margin_source, margin_warnings = _money(
        adapter, account, "marginAvailable", "missing_margin_available"
    )
    used, used_source, used_warnings = _money(adapter, account, "marginUsed", "missing_margin_used")
    unrealised, unrealised_source, unrealised_warnings = _signed_money(adapter, account, "unrealizedPL")
    warnings.extend(balance_warnings)
    warnings.extend(nav_warnings)
    warnings.extend(margin_warnings)
    warnings.extend(used_warnings)
    warnings.extend(unrealised_warnings)
    if balance == NOT_RETURNED:
        missing.append("balance")
    if nav == NOT_RETURNED:
        missing.append("nav")
    if margin == NOT_RETURNED:
        missing.append("margin_available")
    if used == NOT_RETURNED:
        missing.append("margin_used")
    missing.append("account_type")
    missing.append("account_reporting_timestamp")
    body = {
        "record_kind": "account_summary",
        "outcome": "DIAGNOSTIC_RECORDED",
        "account_id_present": "id" in account and bool(str(account.get("id") or "").strip()),
        "account_id_logged": False,
        "home_currency": currency,
        "home_currency_source": currency_source,
        "home_currency_is_gbp": is_gbp,
        "account_type": NOT_RETURNED,
        "account_type_source": UNVERIFIED,
        "balance": balance,
        "balance_source": balance_source,
        "nav": nav,
        "nav_source": nav_source,
        "margin_available": margin,
        "margin_available_source": margin_source,
        "margin_used": used,
        "margin_used_source": used_source,
        "margin_used_operational_capture": "NOT_PARSED_BY_OPERATIONAL_CLIENT",
        "unrealised_pl": unrealised,
        "unrealised_pl_source": unrealised_source,
        "unrealised_pl_operational_capture": "PARSED_BY_account_core_THEN_DROPPED_FROM_SNAPSHOT",
        "account_reporting_timestamp": NOT_RETURNED,
        "account_reporting_timestamp_source": UNVERIFIED,
        "account_identity_verified": False,
        "missing_evidence": missing,
        "validation_warnings": _unique(warnings),
        "executable_order": adapter.NOT_PRODUCED,
    }
    return body, secrets


def _money(adapter: Any, account: dict[str, Any], key: str, missing_code: str) -> tuple[str, str, list[str]]:
    if key not in account or account.get(key) is None or account.get(key) == "":
        return NOT_RETURNED, UNVERIFIED, [missing_code]
    text = adapter.decimal_text(account.get(key))
    if text is None:
        return NOT_RETURNED, UNVERIFIED, ["incorrect_type"]
    amount = Decimal(text)
    if amount < 0:
        return NOT_RETURNED, UNVERIFIED, ["non_positive_value"]
    if key in {"NAV", "balance"} and amount <= 0:
        return text, BROKER_REPORTED, ["non_positive_value"]
    return text, BROKER_REPORTED, []


def _signed_money(adapter: Any, account: dict[str, Any], key: str) -> tuple[str, str, list[str]]:
    if key not in account or account.get(key) is None or account.get(key) == "":
        return NOT_RETURNED, UNVERIFIED, ["missing_unrealised_pl"]
    text = adapter.decimal_text(account.get(key))
    if text is None:
        return NOT_RETURNED, UNVERIFIED, ["incorrect_type"]
    return text, BROKER_REPORTED, []


def _rejected(code: str, warnings: list[str]) -> dict[str, Any]:
    return {
        "record_kind": "failure",
        "outcome": "REJECTED",
        "error_code": code,
        "missing_evidence": ["account_summary"],
        "validation_warnings": _unique(warnings),
        "executable_order": "NOT_PRODUCED",
    }


def _unique(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen
