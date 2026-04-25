---
status: complete
quick_id: 260425-nwj
slug: brochure-trim-pdf
date: 2026-04-25
---

# Brochure PDF — emit at trim size for consumer printers

## Why

After RM-01 fixed the PT_PER_PX scaling, the brochure PDF reported the right inches (11.253 × 8.753) but those dims were the **bleed canvas** — letter-landscape (11 × 8.5) **+ 0.125" bleed on each side**. Print shops want bleed; consumer printers can't fit it. Symptom: when the user printed the PDF on a standard letter sheet, the printer either scaled the page (visible stretching) or padded it (black bars top/bottom) because 11.25 ≠ 11 and 8.75 ≠ 8.5.

## What changed

`flyer_generator/brochure/stages/pdf.py`:
- Page size: `TRIM_WIDTH_PX × TRIM_HEIGHT_PX` (3300 × 2550 px = 792 × 612 pt = **11 × 8.5 in**) instead of `BLEED_CANVAS_*` (3376 × 2626 px = 810.24 × 630.24 pt = 11.25 × 8.75 in)
- `drawImage(... -BLEED_PX, -BLEED_PX, BLEED_CANVAS_WIDTH, BLEED_CANVAS_HEIGHT ...)`: PNG offset by 0.125" so the bleed area extends past the page boundary and clips off, leaving only the trim portion visible
- `_draw_crop_marks` no longer called (crop marks belong in the bleed area which is no longer on the page)
- Caller still rasterizes at the bleed canvas — no upstream contract change

`tests/brochure/test_pdf.py` + `tests/brochure/stages/test_pdf_dimensions.py`:
- Flipped 3 page-size assertions from BLEED dimensions (11.25 × 8.75) to TRIM (11 × 8.5)
- Added explicit anti-regression: mediabox MUST NOT match the bleed-canvas size — that was the symptom the user flagged

## Tradeoff

A future "print-shop" output mode could re-emit the bleed canvas + crop marks behind a `BrochureCreateRequest.print_format: "consumer" | "print_shop"` flag. Not built today — file as a follow-up if a real customer asks. Default behavior is now consumer-printer-friendly.

`_draw_crop_marks` and the `_CROP_LEN`/`_CROP_STROKE` constants are kept in the module (dead code) so the future print-shop mode can reuse them without recovering from git.

## Verification

- `pytest tests/brochure/` — 11/11 brochure pdf tests pass
- Full suite: 1800 passed, 0 failed (no regression vs 260425-mvu baseline)
- Local spot-check: `assemble_brochure_pdf` emits `Page 1: 792.0pt × 612.0pt = 11.00in × 8.50in`
- Live verification deferred to next brochure generation against the recycled worker

## Files

- `flyer_generator/brochure/stages/pdf.py` (page size + drawImage offset; crop-mark call removed)
- `tests/brochure/test_pdf.py` (page-size test renamed + flipped to trim contract)
- `tests/brochure/stages/test_pdf_dimensions.py` (2 page-size tests flipped + anti-bleed assertion added)
