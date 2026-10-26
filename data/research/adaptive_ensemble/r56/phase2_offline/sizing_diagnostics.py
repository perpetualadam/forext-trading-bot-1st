"""Passive record of sizing values supplied by the caller.

This module does not calculate a position, choose a signal, or build an order.
A supplied pip value stays unverified against the broker.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
NOT_SUPPLIED = "NOT_SUPPLIED"
NOT_VERIFIED = "NOT_VERIFIED"
UNVERIFIED = "UNVERIFIED"
NOT_PRODUCED = "NOT_PRODUCED"

_INPUTS = (
    "instrument",
    "proposed_api_units",
    "stop_distance",
    "risk_budget",
    "account_currency",
    "calculated_pip_value",
    "margin_estimate",
)
_KNOWN = set(_INPUTS) | {"conversion_inputs", "sources"}


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
    secrets = adapter.sensitive_literals(document)
    if not isinstance(document, dict):
        return _rejected("incorrect_type"), secrets
    warnings: list[str] = []
    missing: list[str] = []
    if any(key not in _KNOWN for key in document):
        warnings.append("unexpected_fields_dropped")
    sources = document.get("sources") if isinstance(document.get("sources"), dict) else {}
    if "sources" in document and not isinstance(document.get("sources"), dict):
        warnings.append("incorrect_type")
        sources = {}

    values: dict[str, Any] = {}
    source_fields: dict[str, str] = {}
    for name in _INPUTS:
        if name not in document or document.get(name) in (None, ""):
            values[name] = NOT_SUPPLIED
            source_fields[name] = UNVERIFIED
            missing.append(name)
            warnings.append("missing_sizing_input")
            continue
        shown, item_source, item_warnings = _value(adapter, name, document.get(name), sources.get(name))
        values[name] = shown
        source_fields[name] = item_source
        warnings.extend(item_warnings)
        if shown == NOT_SUPPLIED:
            missing.append(name)

    conversion = _conversion(adapter, document.get("conversion_inputs"), sources.get("conversion_inputs"))
    if conversion["status"] != "PRESENT":
        missing.append("conversion_inputs")
        warnings.append("missing_sizing_input")
    warnings.append("pip_value_unverified")
    warnings.append("stake_mapping_unverified")
    missing.append("gbp_pip_value")
    missing.append("stake_to_unit_mapping")
    body = {
        "record_kind": "sizing",
        "outcome": "DIAGNOSTIC_RECORDED",
        "instrument": values["instrument"],
        "instrument_source": source_fields["instrument"],
        "proposed_api_units": values["proposed_api_units"],
        "proposed_api_units_source": source_fields["proposed_api_units"],
        "stop_distance": values["stop_distance"],
        "stop_distance_source": source_fields["stop_distance"],
        "risk_budget": values["risk_budget"],
        "risk_budget_source": source_fields["risk_budget"],
        "account_currency": values["account_currency"],
        "account_currency_source": source_fields["account_currency"],
        "conversion_inputs": conversion,
        "calculated_pip_value": values["calculated_pip_value"],
        "calculated_pip_value_source": source_fields["calculated_pip_value"],
        "gbp_pip_value_status": UNVERIFIED,
        "margin_estimate": values["margin_estimate"],
        "margin_estimate_source": source_fields["margin_estimate"],
        "stake_to_unit_mapping": NOT_VERIFIED,
        "sizing_formula_status": "NOT_REUSED",
        "missing_evidence": _unique(missing),
        "validation_warnings": _unique(warnings),
        "executable_order": NOT_PRODUCED,
        "order_payload": NOT_PRODUCED,
    }
    return body, secrets


def _value(adapter: Any, name: str, value: Any, claimed: Any) -> tuple[Any, str, list[str]]:
    source = claimed if claimed in adapter.FIELD_SOURCES else UNVERIFIED
    warnings: list[str] = []
    if claimed not in adapter.FIELD_SOURCES:
        warnings.append("unverified_field_source")
    if name == "instrument":
        text = adapter.instrument_name(value)
        if text is None:
            return NOT_SUPPLIED, UNVERIFIED, warnings + ["incorrect_type"]
        return text, source, warnings
    if name == "account_currency":
        text = adapter.currency_code(value)
        if text is None:
            return NOT_SUPPLIED, UNVERIFIED, warnings + ["incorrect_type"]
        return text, source, warnings
    text = adapter.decimal_text(value)
    if text is None:
        return NOT_SUPPLIED, UNVERIFIED, warnings + ["incorrect_type"]
    return text, source, warnings


def _conversion(adapter: Any, value: Any, claimed: Any) -> dict[str, Any]:
    source = claimed if claimed in adapter.FIELD_SOURCES else UNVERIFIED
    if value in (None, "", {}):
        return {"status": NOT_VERIFIED, "source": UNVERIFIED}
    if not isinstance(value, dict):
        return {"status": NOT_VERIFIED, "source": UNVERIFIED}
    factor = adapter.decimal_text(value.get("quoted_factor")) if "quoted_factor" in value else None
    pair = adapter.instrument_name(value.get("pair")) if "pair" in value else None
    if factor is None and pair is None:
        return {"status": NOT_VERIFIED, "source": UNVERIFIED}
    shown: dict[str, Any] = {"status": "PRESENT", "source": source}
    if pair is not None:
        shown["pair"] = pair
    if factor is not None:
        shown["quoted_factor"] = factor
    return shown


def _rejected(code: str) -> dict[str, Any]:
    return {
        "record_kind": "failure",
        "outcome": "REJECTED",
        "error_code": code,
        "missing_evidence": ["sizing"],
        "validation_warnings": ["incorrect_type"],
        "executable_order": NOT_PRODUCED,
        "order_payload": NOT_PRODUCED,
    }


def _unique(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen
