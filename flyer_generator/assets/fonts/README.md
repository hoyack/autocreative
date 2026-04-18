# Bundled fonts for brochure templates

Drop open-licensed `.woff2` files into this directory to have them
inlined as `@font-face` data-URIs in the composed brochure SVGs.

## Expected filenames

The loader (`flyer_generator/brochure/stages/fonts.py`) matches files by
the family name declared in each `LayoutTemplate`. Place files as:

| Template family (as declared) | Expected filename |
|-------------------------------|-------------------|
| `Inter` | `Inter.woff2` |
| `Playfair Display` | `Playfair_Display.woff2` |
| `Fredoka` | `Fredoka.woff2` |
| `Source Serif Pro` | `Source_Serif_Pro.woff2` |
| `Avenir Next` | `Avenir_Next.woff2` |
| `Georgia` | `Georgia.woff2` |

The matcher is tolerant: it strips quotes and commas from
`font-family` strings and replaces spaces with underscores before
looking for `<FamilyName>.woff2` in this directory.

Missing files are silently skipped. The system generic fallback
(`serif`, `sans-serif`, etc.) in each template's `*_font_family`
declaration guarantees the SVG still renders — just without the
precise typeface.

## Licensing

Only use fonts under permissive open licenses (SIL OFL 1.1, Apache
2.0, MIT). Retain the license file alongside the `.woff2` under this
directory.

## Subsetting for repo size

Full Latin + extended glyphs can be ~150KB per weight. For brochure
use we only need Latin basic — subset with `pyftsubset`:

```sh
pyftsubset path/to/Inter.ttf \
  --unicodes=U+0020-007E,U+00A0-00FF \
  --flavor=woff2 \
  --output-file=Inter.woff2
```

Typical subsetted size: ~30KB per file.
