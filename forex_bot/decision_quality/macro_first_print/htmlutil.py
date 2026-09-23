"""Minimal HTML-to-text helpers. No third-party HTML parser required."""

from __future__ import annotations

import html as html_lib
import re


def html_to_text(raw: str) -> str:
    text = raw
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"(?i)</tr>", "\n", text)
    text = re.sub(r"(?i)</(h\d|div|li|table)>", "\n", text)
    text = re.sub(r"(?i)</t[hd]>", " | ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
