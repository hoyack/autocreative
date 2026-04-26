You’re thinking about this the right way—don’t start with designs, start with **a generative system that can produce designs**. What you want is essentially a **design grammar + schema contract** that Codex can reliably expand into concrete brochure templates.

Below is a **clean, extensible spec** that defines:

1. The **schema structure**
2. The **design primitives (visual language)**
3. The **layout system**
4. The **10 core template archetypes (not instances, just definitions)**

---

# 🧠 BROCHURE GENERATION SPEC (v1)

## 1. Core Philosophy

Each brochure template is **not a static layout**, but a **parameterized design system** composed of:

* Structured layout zones
* Visual motifs (geometry + layering)
* Content expectations (text/image/illustration)
* Style constraints (density, hierarchy, rhythm)

The system must:

* Support **tri-fold, bi-fold, and single-sheet**
* Be **variant-expandable**
* Encode **composition logic**, not just appearance

---

## 2. Schema Structure (High-Level)

Each template must conform to this structure:

```json
BrochureTemplate {
  id: string,
  name: string,
  category: enum,
  layout_type: enum,
  density: enum,
  visual_style: VisualStyle,
  geometry_system: GeometrySystem,
  color_system: ColorSystem,
  typography_system: TypographySystem,
  layout_zones: LayoutZone[],
  content_strategy: ContentStrategy,
  composition_rules: CompositionRules,
  asset_requirements: AssetRequirements,
  variant_hooks: VariantHooks
}
```

---

## 3. Foundational Systems

### 3.1 Visual Style

```json
VisualStyle {
  tone: ["corporate", "playful", "editorial", "luxury", "technical"],
  contrast_level: "low | medium | high",
  whitespace_usage: "minimal | balanced | spacious",
  layering_depth: "flat | layered | deep"
}
```

---

### 3.2 Geometry System (CRITICAL)

This is your **signature differentiator**.

```json
GeometrySystem {
  primitives: ["rectangle", "circle", "arc", "triangle", "line"],
  overlay_patterns: [
    "offset panel",
    "split diagonal",
    "radial spread",
    "corner anchor",
    "band overlay"
  ],
  interaction_rules: {
    overlap: boolean,
    clipping: boolean,
    transparency: boolean
  },
  anchor_positions: ["left", "right", "top", "bottom", "center"],
  motion_suggestion: "static | directional | radial"
}
```

👉 Example concepts:

* Half-circle bleeding off edge
* Floating white panel with offset shadow block
* Diagonal cut splitting brochure

---

### 3.3 Layout Zones

```json
LayoutZone {
  id: string,
  type: "header | hero | body | sidebar | footer | callout",
  position: "panel-based or relative",
  span: number,
  layering_index: number,
  background: "none | color | image | pattern",
  padding: "tight | medium | loose"
}
```

---

### 3.4 Content Strategy

```json
ContentStrategy {
  primary_focus: "text | image | balanced",
  reading_flow: "linear | modular | exploratory",
  hierarchy_levels: number,
  call_to_action_presence: boolean
}
```

---

### 3.5 Composition Rules

```json
CompositionRules {
  alignment: "grid | asymmetrical | hybrid",
  grid_system: "columns | modular | freeform",
  focal_point_strategy: "single | multiple | distributed",
  visual_weight_distribution: "left-heavy | right-heavy | balanced"
}
```

---

### 3.6 Asset Requirements

```json
AssetRequirements {
  photography: "none | minimal | dominant",
  illustration: "none | minimal | dominant",
  iconography: boolean,
  background_textures: boolean
}
```

---

### 3.7 Variant Hooks (IMPORTANT FOR SCALING)

```json
VariantHooks {
  color_variants: boolean,
  geometry_variants: boolean,
  density_variants: boolean,
  layout_flip: boolean,
  theme_overrides: ["industry-specific", "event-based"]
}
```

---

# 🎨 4. THE 10 CORE TEMPLATE ARCHETYPES

These are **conceptual blueprints**, not designs.

---

## 1. Minimal Panel Overlay

* Clean base with **floating white panel**
* Subtle geometric offset block
* High whitespace

---

## 2. Bold Diagonal Split

* Strong diagonal division
* Two contrasting zones
* Text/image split across axis

---

## 3. Radial Feature (Half-Circle Focus)

* Large arc or circle bleeding off page
* Text layered over curvature
* Directional visual flow

---

## 4. Modular Grid System

* Strict grid layout
* Repeating content blocks
* Highly structured, scalable

---

## 5. Layered Depth Stack

* Multiple overlapping panels
* Shadows / transparency
* Depth-driven hierarchy

---

## 6. Edge-Anchored Geometry

* Shapes anchored to edges/corners
* Content flows inward
* Strong framing effect

---

## 7. Hero Image Dominant

* Full-bleed image
* Minimal text overlay
* Supporting geometric accents

---

## 8. Editorial Spread

* Magazine-style
* Mixed typography scales
* Asymmetrical but balanced

---

## 9. Pattern + Overlay Hybrid

* Background pattern system
* Clean overlay panels for content
* Contrast between busy + calm

---

## 10. Technical / Futuristic Grid

* Fine lines, micro-grid
* Data/diagram feel
* Precision layout with accents

---

# 🧩 5. Cross-Template Dimensions

Each template must define:

* **Density Level**

  * Minimal
  * Medium
  * Dense

* **Primary Asset Type**

  * Photography
  * Illustration
  * Mixed

* **Geometry Intensity**

  * Subtle
  * Moderate
  * Dominant

---

# 🔁 6. Expansion Strategy (Future)

Each core template should later expand into:

```
Core Template
  → Industry Variant (Healthcare, Tech, Events, etc.)
  → Density Variant (Minimal vs Busy)
  → Asset Variant (Photo vs Illustration)
  → Color Variant (Light/Dark/Brand)
```

---

# ⚙️ 7. Codex Generation Intent

When you hand this to Codex later, it should:

* Instantiate **10 JSON objects**
* Each strictly conforming to schema
* Each mapped to one archetype
* Each with:

  * Unique geometry system
  * Defined layout zones
  * Clear composition rules

---

# 💡 Final Insight (Important)

What you’re building is **not brochure templates**.

You’re building:

> A **procedural design engine** for brochures.

The geometry system + layout zones + composition rules =
👉 a **design language that can scale infinitely**

---

If you want next step, I’d recommend:

* Converting this into a **strict JSON Schema (Draft 7/2020-12)**
* Then generating **1 fully realized example** to validate Codex behavior before scaling to 10

Or we can go deeper into:
👉 “how Codex should *interpret* and render these into actual layouts” (that’s where this gets really powerful)
