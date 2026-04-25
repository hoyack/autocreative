---
status: complete
quick_id: 260425-mvu
slug: brochure-directives-fix
date: 2026-04-25
---

# Brochure cover directives — strip text-priming function-words

## Why

Brochure hero generation was failing 3/3 vision-gate attempts even with safe nature-themed `hero_concept` prompts. Comfy kept baking garbled text ("Diktric Preklihy", "Botch Deuct", "FHILT& STACLIS") into otherwise reasonable forest / dewdrops / sunset images. The vision gate then correctly rejected them and the renderer fell back to a placeholder. Compare with `FLYER_DIRECTIVES` which never has this problem.

Root cause (user-spotted): `BROCHURE_COVER_DIRECTIVES` contained text-priming function-words.

```
- "Clean, low-detail areas along the left and right edges for title and subtitle overlay."
- "Soft gradient or calm sky toward the top third to anchor a large overlaid headline."
```

Words like *title*, *subtitle*, *headline*, *overlay* (and *brochure*, *flyer*, *card*, *poster*) bias SDXL-class models to bake text into the output even with a strong negative prompt — the model was trained on stock-photo data where those words are paired with text-in-image. The negative prompt loses the tug-of-war.

## What changed

`flyer_generator/brochure/stages/prompt_builder.py`:

```diff
 BROCHURE_COVER_DIRECTIVES: list[str] = [
+    # Mirror FLYER_DIRECTIVES: describe the IMAGE shape, never the function it serves.
+    # ...
     "Landscape composition, 16:9 aspect ratio.",
     "Main subject centred in the middle third of the frame.",
-    "Clean, low-detail areas along the left and right edges for title and subtitle overlay.",
-    "Soft gradient or calm sky toward the top third to anchor a large overlaid headline.",
-    "No text, no writing, no letters, no signs, no graphic design elements.",
+    "Smooth clean bokeh areas along the left and right edges of the frame.",
+    "Soft gradient or calm sky in the upper third of the frame.",
+    "No text, no writing, no letters, no signs, no symbols.",
+    "Pure background art with no graphic design elements.",
     "Visually balanced — no single corner dominating attention.",
 ]
```

`tests/brochure/test_prompt_builder.py`:
- Flipped `test_positive_prompt_contains_brochure_directives_not_flyer` to check the real differentiator (portrait-only directive must NOT appear in brochure prompt) instead of strict mutual exclusion. Anti-text language now intentionally shared between flyer + brochure.
- Added `test_directives_have_no_text_priming_function_words` regression guard against `{title, subtitle, headline, overlay, overlaid, brochure, flyer, card, magazine, poster}` reappearing in the directives.

## Verification

- `pytest tests/brochure/test_prompt_builder.py -v` — 10/10 pass
- Full suite: 1800 passed, 0 failed (1799 baseline + 1 new regression test)
- Live verification deferred to next brochure generation against the running stack

## Memory captured

Saved `feedback_comfy_prompt_engineering.md` so future sessions don't write the same kind of prompt builder for invitation/poster/social.

## Files

- `flyer_generator/brochure/stages/prompt_builder.py` (modified)
- `tests/brochure/test_prompt_builder.py` (test flipped + regression test added)
