"""Text fit + measurement math tests."""

from __future__ import annotations

from flyer_generator.brochure.schema_renderer.text_fit import (
    char_budget_for_bbox,
    chars_per_line,
    fit_to_bbox,
    measure_text,
    wrap_text,
)


def test_measure_text_scales_with_font_size():
    _, h_small = measure_text("Hello", 24)
    _, h_big = measure_text("Hello", 72)
    assert h_big == 3 * h_small


def test_measure_longer_text_is_wider():
    w1, _ = measure_text("Hi", 36)
    w2, _ = measure_text("Hello World!", 36)
    assert w2 > w1


def test_chars_per_line_positive():
    assert chars_per_line(1000, 36) > 0
    # Narrower bbox = fewer chars
    assert chars_per_line(200, 36) < chars_per_line(1000, 36)
    # Larger font = fewer chars
    assert chars_per_line(1000, 72) < chars_per_line(1000, 36)


def test_wrap_text_splits_words():
    lines = wrap_text("The quick brown fox jumps over the lazy dog", 20)
    assert lines[0].startswith("The quick")
    # Every line <= 20 chars
    assert all(len(line) <= 20 for line in lines)


def test_wrap_text_preserves_paragraph_breaks():
    lines = wrap_text("First line\n\nSecond paragraph here", 40)
    # Empty string indicates paragraph break between them
    assert "" in lines


def test_wrap_text_hard_breaks_long_words():
    lines = wrap_text("supercalifragilisticexpialidocious", 10)
    assert all(len(line) <= 10 for line in lines)


def test_wrap_empty_text():
    assert wrap_text("", 20) == []


def test_fit_to_bbox_truncates_at_height():
    text = "word " * 200  # many words
    fit = fit_to_bbox(text, (0, 0, 300, 200), font_size=36, line_height=46)
    max_lines_possible = 200 // 46  # 4
    assert len(fit.lines) <= max_lines_possible
    assert fit.overflowed


def test_fit_to_bbox_does_not_overflow_short_text():
    fit = fit_to_bbox("short", (0, 0, 500, 500), font_size=36, line_height=46)
    assert not fit.overflowed
    assert len(fit.lines) >= 1


def test_char_budget_scales_with_bbox_size():
    small = char_budget_for_bbox((0, 0, 300, 200), 36, 46)
    large = char_budget_for_bbox((0, 0, 1000, 2000), 36, 46)
    assert large > small * 4


def test_fit_to_bbox_zero_height_degenerate():
    fit = fit_to_bbox("hello", (0, 0, 500, 0), font_size=36, line_height=46)
    assert fit.lines == []
    assert fit.overflowed
