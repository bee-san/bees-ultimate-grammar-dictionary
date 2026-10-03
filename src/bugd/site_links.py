"""Stable page addresses shared by the website and both dictionary editions."""

from __future__ import annotations

import hashlib

SITE_URL = "https://bee-san.github.io/bees-ultimate-grammar-dictionary"


def grammar_slug(expression: str) -> str:
    return hashlib.sha256(expression.encode("utf-8")).hexdigest()[:20]


def grammar_path(expression: str, *, english: bool = False) -> str:
    return f"{'en/' if english else ''}grammar/{grammar_slug(expression)}/"


def grammar_url(expression: str, *, english: bool = False) -> str:
    return f"{SITE_URL}/{grammar_path(expression, english=english)}"
