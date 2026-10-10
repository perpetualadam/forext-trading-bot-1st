"""Local .dockerignore approximation.

This follows the documented pattern rules used by Docker's context matcher:
comments, last-match-wins, `!` exceptions, `**`, and `*` that does not cross `/`.
A pattern with no slash matches the basename in any directory.
A match on a parent directory excludes its children unless a later exception matches.
This is not a running Docker daemon. It does not prove BuildKit's behaviour.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _regex(pattern: str) -> re.Pattern[str]:
    parts: list[str] = []
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            parts.append("(?:.*/)?")
            index += 3
            continue
        if pattern.startswith("**", index):
            parts.append(".*")
            index += 2
            continue
        char = pattern[index]
        if char == "*":
            parts.append("[^/]*")
        elif char == "?":
            parts.append("[^/]")
        elif char == "[":
            end = pattern.find("]", index + 1)
            if end != -1:
                parts.append(pattern[index : end + 1])
                index = end + 1
                continue
            parts.append(re.escape(char))
        else:
            parts.append(re.escape(char))
        index += 1
    return re.compile("^" + "".join(parts) + "$")


def parse_dockerignore(text: str) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        body = line[1:] if negated else line
        body = body.replace("\\", "/").strip()
        directory_only = body.endswith("/")
        if directory_only:
            body = body[:-1]
        anchored = body.startswith("/")
        body = body.lstrip("/")
        if not body:
            continue
        rules.append(
            {
                "negated": negated,
                "anchored": anchored,
                "directory_only": directory_only,
                "pattern": body,
                "unanchored_basename": "/" not in body and not anchored,
                "regex": _regex(body),
            }
        )
    return rules


def _normal(path: str) -> str:
    return path.replace("\\", "/").lstrip("/")


def _rule_matches(rule: dict[str, Any], path: str) -> bool:
    if rule["unanchored_basename"]:
        parts = path.split("/")
        return any(rule["regex"].match(part) for part in parts)
    if rule["regex"].match(path):
        return True
    parts = path.split("/")
    for index in range(1, len(parts)):
        if rule["regex"].match("/".join(parts[:index])):
            return True
    return False


def context_excluded(path: str, rules: list[dict[str, Any]]) -> bool:
    """Return True when the last matching rule excludes the path."""
    rel = _normal(path)
    if not rel or rel.startswith("../") or "/../" in f"/{rel}":
        return True
    excluded = False
    for rule in rules:
        if _rule_matches(rule, rel):
            excluded = not rule["negated"]
    return excluded


def load_repo_rules(root: Path | None = None) -> list[dict[str, Any]]:
    base = root or Path(__file__).resolve().parents[3]
    return parse_dockerignore((base / ".dockerignore").read_text(encoding="utf-8"))
