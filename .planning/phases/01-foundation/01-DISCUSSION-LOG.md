# Phase 1: Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-16
**Phase:** 01-foundation
**Mode:** Auto (all recommended defaults selected)
**Areas discussed:** Project structure, Preset data format, Zone coordinate system

---

## Project Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Flat module layout per spec.md | Follow docs/spec.md Section 3 exactly | ✓ |
| Alternative layout | Custom organization | |

**User's choice:** Flat module layout per spec.md (auto-selected recommended default)
**Notes:** Spec already defines a clear, well-reasoned module structure. No reason to deviate.

---

## Preset Data Format

| Option | Description | Selected |
|--------|-------------|----------|
| Pydantic models in presets.py | StylePreset BaseModel + PresetRegistry class | ✓ |
| YAML/JSON config files | External preset definitions loaded at runtime | |
| Inline dicts | Simple dictionaries without class wrapping | |

**User's choice:** Pydantic models in presets.py (auto-selected recommended default)
**Notes:** Matches spec design. Pydantic provides validation and type safety for preset data.

---

## Zone Coordinate System

| Option | Description | Selected |
|--------|-------------|----------|
| Static dict in zones.py | ZoneName → ZoneCoord mapping with fixed pixel values | ✓ |
| Computed from canvas dimensions | Calculate coordinates dynamically | |

**User's choice:** Static dict in zones.py (auto-selected recommended default)
**Notes:** Fixed 1080x1920 canvas means static coordinates are simpler and faster. Spec defines exact pixel values.

---

## Claude's Discretion

- structlog initialization details
- `__init__.py` public API surface ordering
- Test fixture organization

## Deferred Ideas

None
