# Feature Landscape

**Domain:** AI-powered event flyer/poster generation (CLI + module)
**Researched:** 2026-04-16

## Table Stakes

Features users expect. Missing = product feels incomplete or unusable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| AI background image generation from text prompt | Every competitor (Canva Magic Design, Adobe Express, Pixazo, PosterMyWall) generates images from prompts. Without this the tool is just a template filler. | High | ComfyCloud + Lumina2 already chosen. Core pipeline stage. |
| Text overlay on generated background | Fundamental purpose of a flyer -- event info must appear on the image. All tools do this. | Medium | SVG composition approach is solid. Pillow + cairosvg rasterization. |
| Multiple style presets | Canva offers thousands of templates; Adobe Express has style categories. Users expect variety without manual prompt engineering. | Low | 6 presets defined (photorealistic, anime, western_cartoon, scifi, watercolor, retro_poster). Sufficient for MVP. |
| Correct output resolution (1080x1920) | Standard Instagram Story / print-ready portrait format. Users expect pixel-perfect output. | Low | 832x1472 latent upscaled to 1080x1920 via Pillow. Straightforward. |
| Text readability against any background | Industry standard: 4.5:1 contrast ratio minimum. Canva and Adobe auto-optimize contrast. If text is unreadable, the flyer is worthless. | Medium | Scrim gradients + adaptive text color (white/dark) based on vision analysis. |
| Event data fields (title, date, venue, fee, org) | Every event flyer tool handles these core fields. Missing any = incomplete flyer. | Low | Already in EventInput model. |
| PNG export | Standard output format across all tools. PDF is nice-to-have; PNG is mandatory. | Low | cairosvg rasterizes SVG to PNG. Done. |
| CLI interface | For a developer tool, CLI is table stakes. Canva/Adobe are GUI, but this product targets automation pipelines. | Low | Typer-based CLI with `--list-presets`, `--dry-run`, JSON input. |
| Structured error handling | Automation tools must fail predictably. Silent failures or cryptic errors make the tool unusable in pipelines. | Medium | Typed exception hierarchy planned. Essential for non-interactive use. |

## Differentiators

Features that set this product apart from Canva/Adobe/PosterMyWall GUI tools and from simpler template-based APIs like Bannerbear.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Vision-driven layout (Claude vision for zone detection) | **Key differentiator.** Most tools use template grids or fixed zones. This tool uses a VLM to *look at* the generated background and decide where text should go. Adapts to every unique background. No template lock-in. Research shows this is cutting-edge -- academic papers (PosterIQ, AutoPP, TextLap) explore this but few production tools do it. | High | Single Claude vision call returns: approval, zone coordinates, text color recommendation. This is the architectural innovation. |
| Regeneration loop with vision feedback | Most tools generate once and let the user manually retry. This tool auto-rejects unsuitable backgrounds and feeds refinement hints back to the image generator. Up to N retries with progressive improvement. Academic research confirms iterative refinement yields ~17.8% quality improvement over 3 cycles. | High | Vision rejection triggers re-generation with refinement hints. Requires careful prompt engineering for the feedback loop. |
| Adaptive text color from vision analysis | Rather than fixed white or black text, the vision model recommends color based on actual background luminance in the text zones. Goes beyond simple light/dark detection. | Medium | Part of the single vision call. Low marginal cost since vision is already being called. |
| Zone-specific scrim gradients | Instead of a uniform overlay (the typical 20-40% opacity approach), scrims are generated per-zone based on where text actually lands. More visually sophisticated than blanket darkening. | Medium | SVG gradient elements positioned per vision-derived coordinates. |
| Title auto-sizing with widow-line merge | Smart typography: text wraps to fill available zone, avoids orphan/widow lines that look amateurish. Most automated tools don't handle this. | Medium | Word-wrap algorithm with merge logic. Needs testing across title lengths. |
| Fee badge pill shape | Dynamic-width pill badge for pricing info. Small touch but signals design quality. | Low | SVG rounded rect with text measurement for width. |
| Importable Python API | Unlike GUI tools (Canva, Adobe) or template APIs (Bannerbear), this is a first-class Python library. `generate_flyer()` can be called from any Python pipeline -- FastAPI, Celery workers, Airflow DAGs. | Medium | Public API surface: `generate_flyer()`, `FlyerGenerator`, `EventInput`, `FlyerOutput`. |
| Custom preset registration | Users can define their own style presets via `PresetRegistry`. No competitor API offers this level of style customization without a visual editor. | Low | Registry pattern. Extension point for power users. |
| Structured logging with trace IDs | Production-grade observability. When generating hundreds of flyers, you need to trace failures per-flyer. GUI tools don't need this; automation tools absolutely do. | Low | structlog with JSON output and trace_id binding. |

## Anti-Features

Features to explicitly NOT build. These are tempting but would dilute focus, add complexity, or conflict with the product's architecture.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Interactive GUI / web editor | Canva and Adobe own this space with massive template libraries, drag-and-drop, and brand kits. Competing here is a losing game. This tool's value is *zero-touch automation*. | Expose importable API. Let others wrap with FastAPI/Streamlit if they want a UI. |
| Template library / marketplace | Bannerbear's model: design templates visually, fill programmatically. Requires a visual editor, template storage, versioning. Enormous scope. | Style presets + custom preset registration. Presets are code, not visual templates. |
| Font diversity / custom font upload | Supporting arbitrary fonts requires font rendering pipeline, licensing concerns, fallback chains, CJK/RTL support. Arial/Helvetica covers 90% of event flyers. | Stick with Arial/Helvetica fallback chain. System fonts, reliable rendering. |
| Multi-language / RTL / CJK text layout | Massively increases text rendering complexity (BiDi algorithm, CJK line-breaking, vertical text). Not needed for initial English-focused use case. | Document as future extension point. Don't architect against it, but don't build it. |
| NSFW / content safety moderation | Vision checks suitability for text placement, not content moderation. Adding safety classification is a different problem domain with different models and liability. | Rely on ComfyCloud's upstream safety. Vision evaluates *layout suitability*, not content safety. |
| Batch orchestration | Tempting to add "generate 50 flyers" mode. But orchestration (retry, parallelism, rate limiting, progress tracking) is a separate concern. | Single-flyer generation is the unit. Let Celery/Airflow/n8n handle batching. |
| Animation / video output | Some tools (Bannerbear, Canva) generate animated content. Different rendering pipeline, different output formats, different complexity tier. | PNG only. SVG intermediate is static by design. |
| Image caching layer | Caching generated backgrounds or final outputs saves money on re-runs. But cache invalidation, storage, and key strategy are complex. | Belongs at the orchestration layer, not inside the generator. |
| A/B testing / variation scoring | Generating multiple variants and scoring them against each other. Interesting but adds 3-5x cost per flyer and requires a scoring model. | Single generation with vision-guided quality. The regeneration loop already handles quality. |

## Feature Dependencies

```
Style Presets -----> AI Background Generation (presets drive prompts)
                          |
                          v
                    Claude Vision Evaluation
                     /        |         \
                    v         v          v
            Zone Detection  Color    Approval/Rejection
                |          Decision       |
                v             |           v
          SVG Composition <---+    Regeneration Loop
                |                  (feeds back to generation)
                v
          Title Auto-Sizing
          Fee Badge Pill
          Scrim Gradients
                |
                v
          PNG Rasterization (cairosvg)
                |
                v
          Final Output (1080x1920 PNG)
```

Key dependency chains:
- **Vision evaluation depends on background generation** -- cannot evaluate what doesn't exist
- **SVG composition depends on vision output** -- zone coordinates, color, approval all come from vision
- **Regeneration loop depends on vision rejection** -- the loop is triggered by vision saying "no"
- **Auto-sizing depends on zone dimensions** -- title sizing adapts to the zone vision identified
- **Scrim gradients depend on zone coordinates** -- scrims are positioned where text will go
- **Custom presets depend on preset registry** -- registry must exist before custom presets can register

## MVP Recommendation

**Prioritize (Phase 1 -- must work end-to-end):**

1. AI background generation via ComfyCloud (table stakes, everything depends on it)
2. Claude vision evaluation for zones + color + approval (the core differentiator)
3. SVG composition with text overlay using vision-derived zones (table stakes)
4. Adaptive text color and scrim gradients (table stakes readability)
5. PNG rasterization at 1080x1920 (table stakes output)
6. CLI entrypoint with basic arguments (table stakes for developer tool)
7. Structured error handling (table stakes for automation)

**Prioritize (Phase 2 -- polish and robustness):**

1. Regeneration loop with vision feedback (differentiator, but needs Phase 1 working first)
2. Title auto-sizing and widow-line merge (differentiator, improves quality)
3. Fee badge pill shape (differentiator, small scope)
4. All 6 style presets (table stakes, but 1-2 presets suffice for Phase 1 validation)
5. `--list-presets`, `--dry-run`, JSON file input (CLI completeness)
6. Structured logging with trace IDs (differentiator for production use)

**Defer (Phase 3 -- extensibility):**

1. Custom preset registration via `PresetRegistry` (differentiator, power-user feature)
2. Importable public API polish (`generate_flyer()`, `FlyerGenerator`) (differentiator, needs stable internals first)
3. Pydantic Settings for env-var config (nice-to-have, can use simple env vars initially)

**Explicitly defer to "never" or "different project":**

- GUI, templates, font diversity, multi-language, batch orchestration, animation, caching, A/B testing

## Sources

- [Top 10 AI Poster & Flyer Design Tools (2026) - DevOpsSchool](https://www.devopsschool.com/blog/top-10-ai-poster-flyer-design-tools-in-2025-features-pros-cons-comparison/) - Confidence: MEDIUM
- [6 Best AI-Powered Flyer Maker Tools (2026) - PosterMyWall](https://www.postermywall.com/blog/2025/12/24/6-best-ai-powered-flyer-maker-tools-for-2026/) - Confidence: MEDIUM
- [Bannerbear API - Programmatic Image Generation](https://www.bannerbear.com/) - Confidence: HIGH (official docs)
- [Common Flyer Design Mistakes - DesignWiz](https://designwiz.com/blog/common-flyer-design-mistakes/) - Confidence: MEDIUM
- [AutoPP: Automated Product Poster Generation - arXiv](https://arxiv.org/html/2512.21921) - Confidence: HIGH (academic)
- [PosterIQ: Design Benchmark for Poster Understanding - arXiv](https://arxiv.org/html/2603.24078) - Confidence: HIGH (academic)
- [TextLap: Text-to-Layout Planning - arXiv](https://arxiv.org/html/2410.12844v1) - Confidence: HIGH (academic)
- [Automatic Evaluation of Legibility for Graphic Design Posters - Springer](https://link.springer.com/chapter/10.1007/978-3-031-90167-6_24) - Confidence: HIGH (academic)
- [Skywork AI vs Canva vs Adobe Express Comparison](https://skywork.ai/blog/ai-image/skywork-ai-vs-canva-vs-adobe-express-free-ai-flyer-design) - Confidence: MEDIUM
- [Vision-Guided Iterative Refinement - arXiv](https://arxiv.org/html/2604.05839v1) - Confidence: HIGH (academic)
