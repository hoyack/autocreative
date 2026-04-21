"""Flesch-Kincaid readability heuristic (dependency-free).

Per 19-RESEARCH.md §Readability Heuristic: within +/-0.5 grade levels of textstat
on normal English prose. Warn-severity signal only; not a gate.
"""

from __future__ import annotations

import re

_VOWEL_GROUP_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)
_SENTENCE_END_RE = re.compile(r"[.!?]+")
_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'-]*\b")


def _count_syllables(word: str) -> int:
    """Conservative heuristic: count vowel groups, subtract silent-e, floor at 1."""
    w = word.lower().strip("'-")
    if not w:
        return 0
    n = len(_VOWEL_GROUP_RE.findall(w))
    if w.endswith("e") and n > 1:
        n -= 1
    if w.endswith("le") and len(w) > 2 and w[-3] not in "aeiouy":
        n += 1
    return max(1, n)


def flesch_kincaid_grade(text: str) -> float:
    """Flesch-Kincaid grade level. Higher = harder to read. 12 = senior high."""
    words = _WORD_RE.findall(text)
    n_words = len(words)
    if n_words == 0:
        return 0.0
    n_sentences = max(1, len(_SENTENCE_END_RE.findall(text)))
    n_syllables = sum(_count_syllables(w) for w in words)
    return 0.39 * (n_words / n_sentences) + 11.8 * (n_syllables / n_words) - 15.59
