"""Normalization helpers for HTML imports."""

from __future__ import annotations

import html
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

_WHITESPACE_RE = re.compile(r"\s+")
_RESPONSE_RE = re.compile(r"(?:response|answer|question)\s*([0-9]+)", re.IGNORECASE)


def normalize_header(value: str | None) -> str:
    if value is None:
        return ""
    text = html.unescape(value).replace("\xa0", " ")
    return _WHITESPACE_RE.sub(" ", text).strip()


def normalize_lookup_key(value: str | None) -> str:
    text = normalize_header(value)
    text = text.replace("-", " ").replace("_", " ").replace("/", " ").replace(".", " ")
    return _WHITESPACE_RE.sub(" ", text).strip().casefold()


def normalize_text_cell(value: str | None) -> str:
    if value is None:
        return ""
    text = html.unescape(value).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).strip("\n")


def parse_datetime_text(value: str | None) -> tuple[datetime | None, str | None, tuple[str, ...]]:
    raw = normalize_text_cell(value)
    if not raw:
        return None, None, ()
    formats = (
        "%d %b %Y %I:%M %p",
        "%d %b %Y %H:%M",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
    )
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt), raw, ()
        except ValueError:
            continue
    return None, raw, (f"Could not parse datetime value '{raw}'",)


def parse_duration_text(value: str | None) -> tuple[int | None, str | None, tuple[str, ...]]:
    raw = normalize_text_cell(value)
    if not raw:
        return None, None, ()
    clock_match = re.fullmatch(r"(?:(\d+):)?(\d{1,2}):(\d{2})", raw)
    if clock_match:
        hours = int(clock_match.group(1) or 0)
        minutes = int(clock_match.group(2))
        seconds = int(clock_match.group(3))
        return hours * 3600 + minutes * 60 + seconds, raw, ()
    units = re.findall(r"(\d+)\s*(hour|hours|hr|hrs|minute|minutes|min|mins|second|seconds|sec|secs)", raw.casefold())
    if not units:
        return None, raw, (f"Could not parse duration value '{raw}'",)
    total = 0
    for amount, unit in units:
        number = int(amount)
        if unit.startswith(("hour", "hr")):
            total += number * 3600
        elif unit.startswith(("minute", "min")):
            total += number * 60
        else:
            total += number
    return total, raw, ()


def parse_grade_text(value: str | None) -> tuple[Decimal | None, Decimal | None, str | None, tuple[str, ...]]:
    raw = normalize_text_cell(value)
    if not raw:
        return None, None, None, ()
    if raw.casefold() in {"not yet graded", "blank", "n/a", "na", "none"}:
        return None, None, raw, ()
    if "/" in raw:
        left, right = raw.split("/", 1)
        try:
            return Decimal(left.strip()), Decimal(right.strip()), raw, ()
        except (InvalidOperation, ValueError):
            return None, None, raw, (f"Could not parse grade value '{raw}'",)
    try:
        return Decimal(raw), None, raw, ()
    except (InvalidOperation, ValueError):
        return None, None, raw, (f"Could not parse grade value '{raw}'",)


def extract_response_number(value: str | None) -> int | None:
    match = _RESPONSE_RE.search(normalize_lookup_key(value))
    return int(match.group(1)) if match else None
