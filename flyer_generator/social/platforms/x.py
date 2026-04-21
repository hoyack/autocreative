"""Twitter/X alias -- ``x`` is the 2024+ rebrand. Re-exports twitter.RULES and validate()."""

from __future__ import annotations

from flyer_generator.social.platforms.twitter import RULES, validate

__all__ = ["RULES", "validate"]
