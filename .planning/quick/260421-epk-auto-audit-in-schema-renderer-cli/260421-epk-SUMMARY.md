---
status: complete
quick_id: 260421-epk
slug: auto-audit-in-schema-renderer-cli
completed: 2026-04-21
---

# Quick Task 260421-epk — Auto-audit in schema_renderer CLI

## What shipped

`flyer_generator/brochure/schema_renderer/__main__.py` now runs `audit_render` on both sheets automatically after rasterize and writes `audit.json` to the output directory by default. Three new CLI flags:

| Flag | Default | Behavior |
|------|---------|----------|
| `--audit / --no-audit` | `--audit` | Run adversarial audit after rasterize |
| `--iterate-audit N` | `0` | Run iterate_audit_loop up to `min(N, 3)` cycles if issues found |
| `--audit-json PATH` | `<output>/audit.json` | Override sidecar path |

Per-sheet stderr summary prints one line per sheet:
```
Audit [outside]: AA pass=True (0/7 fail), density=0.68, whitespace_max=0.92, issues=3 (1 warn, 2 info)
Audit [inside]: AA pass=True (0/6 fail), density=0.81, whitespace_max=0.79, issues=1 (0 warn, 1 info)
```

## Scope decision

Density remediation (tighter-budget regen) is deferred until `text_gen.generate_content_from_prompt` grows a per-key budget-override kwarg. Until then, `iterate_audit_loop` runs with contrast-swap remediation only when `--brand-kit` is supplied. Without a brand kit, iterate is a no-op. Documented inline in `__main__.py` so the next contributor can pick it up.

## Tests

9 new tests in `tests/brochure/schema_renderer/test_auto_audit.py`:
- default `--audit` writes audit.json with expected shape
- `--no-audit` skips sidecar
- stderr surfaces warn+ severity (info stays quiet)
- `--iterate-audit 0` runs single pass, no re-render
- `--iterate-audit 1` fires iterate loop when issues present
- `--audit-json` custom path honored
- audit works without `--brand-kit` (graceful kit-absent path)

**Full suite:** 921 passing, 2 deselected slow, zero regressions from 912 baseline.

## Commit

`a976152` — feat(260421-epk): auto-audit every schema_renderer render

## Plan

[260421-epk-PLAN.md](./260421-epk-PLAN.md)
