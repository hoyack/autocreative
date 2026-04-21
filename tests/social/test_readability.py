"""Per checker B1: direct-module imports only."""

from __future__ import annotations

from flyer_generator.social.readability import _count_syllables, flesch_kincaid_grade


def test_count_syllables_common_words() -> None:
    assert _count_syllables("bike") == 1
    assert _count_syllables("simple") == 2
    assert _count_syllables("ukulele") == 3
    assert _count_syllables("") == 0
    assert _count_syllables("I") == 1


def test_flesch_kincaid_empty_is_zero() -> None:
    assert flesch_kincaid_grade("") == 0.0


def test_flesch_kincaid_simple_sentence_low_grade() -> None:
    grade = flesch_kincaid_grade("The cat sat on the mat.")
    assert grade < 5.0


def test_flesch_kincaid_complex_sentence_higher_grade() -> None:
    # Long polysyllabic academic prose
    text = (
        "The phenomenological interpretation of institutional epistemologies necessitates "
        "a reconceptualization of hermeneutic methodologies. Consequently, multidimensional "
        "analysis frameworks must accommodate interdisciplinary perspectives on sociocultural "
        "transformation processes."
    )
    grade = flesch_kincaid_grade(text)
    assert grade > 12.0
