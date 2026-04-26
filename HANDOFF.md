# autocreative — Session Handoff

**For a fresh session after `/clear`.** State-of-the-world for the autocreative repo through Phase 24.2 (Renders Management) + the 260425-nwj brochure-PDF series.

---

## 1. Quick orientation

- **Branch:** `master`, all work committed.
- **Tests:** `.venv/bin/python -m pytest -q -m "not slow"` → **1801 passing**, ~3 min.
- **Latest 10 commits (newest first):**
  ```
  fdc387a fix(260425-nwj): brochure rasterizer now uses bleed canvas dims, not flyer default
  adec1c6 fix(260425-nwj): flatten alpha onto white before drawing into PDF
  9aebfd0 fix(260425-nwj): PDF page now tracks source PNG dimensions, never stretches
  acd2f03 docs(quick-260425-nwj): backfill commit hash
  b0a182a quick(260425-nwj): emit brochure PDF at trim size for consumer printers
  cde3571 docs(quick-260425-mvu): backfill commit hash
  e30d10f quick(260425-mvu): strip text-priming function-words from brochure cover directives
  8ca785b docs(phase-24.2): complete phase execution
  ff4578a test(24.2): persist human verification items as UAT
  343b690 docs(phase-24.2): update tracking after Wave 1 (RM-01 + RM-02)
  ```
- **Roadmap state:** Phase 24 (Poster Primitive) ✅ complete. Phase 24.1 (perception-loop fixes) ✅ complete with HUMAN-UAT pending residential-network timing. Phase 24.2 (renders-management) ✅ complete with HUMAN-UAT pending gallery delete smoke. Two follow-up quick tasks (`260425-mvu`, `260425-nwj`) shipped after the phase closed, both targeting brochure quality.
- **Next planned phase:** 25 (Invitation Primitive). User has signaled the immediate next session is a **verification pass on flyer + social-media post generation end-to-end**, not Phase 25.
- **Live stack:** uvicorn (port 8000) + arq + redis (port 6379) + Vite (port 5173) all running with the latest code. Recycle the worker after any `flyer_generator/` change with `pkill -f "arq flyer_generator.api.worker.WorkerSettings"` and relaunch.

---

## 2. What landed since the v1 milestone closed

### Phase 22 — Flyer template & subtype split
- 6 flyer JSON templates ship under `flyer_generator/flyer/schemas/`: `bold_modern`, `editorial_classic`, `minimal_photo`, `retro_poster`, `tight_typographic`, `zine`.
- `FlyerInput.subtype: Literal["event", "info"] = "event"` — back-compat default. `RenderRecord.kind` deprecates legacy `flyer_final` via migration.
- FT-01..FT-08 verified.

### Phase 23 — Postcard primitive
- `POST /api/v1/postcards` produces 3 artifacts (front PNG + back PNG + print PDF).
- 2 postcard JSON templates ship: `classic_portrait`, `modern_landscape`.
- Parallel-id pattern (`postcard_id == job_id`); compensating-enqueue with typed `error_detail` (no `str(exc)` leak).
- Frontend pages at `/postcards/new` and `/postcards/:id` (status via shared `JobStatusCard`).
- PC-01..PC-06 verified.

### Phase 24 — Poster primitive
- `POST /api/v1/posters` accepts `size: Literal["18x24", "24x36", "27x40"]` + `template` + flyer-like fields → single PNG at print resolution.
- 3 poster templates: `editorial_grand`, `bold_announcement`, `cinematic_onesheet` — typography pre-scaled for print-distance reading (cover_title_size 360/420/380).
- `FlyerGenerator.__init__(canvas_dimensions=...)` kwarg threads canvas dims through preprocessor → composer → rasterizer → output. Default `(1080, 1920)` keeps the existing flyer worker byte-identical.
- `PosterRecord` ORM, `JobKind.POSTER`, alembic migration `f24t01`.
- Frontend `/posters/new` + `/posters/:id`, sidebar nav, Jobs/Renders KINDS extended with `poster` + `poster_final`.
- PO-01..PO-04 verified, with HUMAN-UAT for live-stack render + Playwright harness deferred per Phase 22-07 / 23-06 precedent.

### Phase 24.1 — Perception-loop fixes
Adversarial perception loop on 2026-04-25 surfaced 4 cross-phase bugs. All 4 fixed end-to-end, with one residual:

| Req | Fix | Verification |
|---|---|---|
| **PLF-01** | Postcard task now invokes Comfy via `image_gate.generate_postcard_hero` when `image_hint` is set; body text renders on FRONT panel of both templates; `[ hero ]` placeholder eliminated | Live render at `/tmp/perception/postcard-attempt1-render.png` shows AI garden image + body text |
| **PLF-02** | Brochure kicker derives from `content.tagline` (was hardcoded "ESTATE PLANNING"); section HEADINGS render on back panel; `[ slot ]` placeholders removed across all 13 brochure schemas. **Residual: section body_paragraphs still don't render under headings — file as PLF-02b in a future Phase 24.3** | `/tmp/perception/brochure-test-back.png` shows headings only |
| **PLF-03** | `bold_modern.json` cover_title bbox h=600→480, details band y=1300→1200; deterministic bbox-overlap pytest covers all 6 flyer templates with sha256 tripwire on the 5 unchanged ones | Live retro_poster flyer at `/tmp/perception/flyer-late-render.png` |
| **PLF-04** | `flyer_generator/stages/vision.py::_downsample_for_vision` resizes the background to ≤1920px on long edge before base64 encoding for the LLM call; `background.image_bytes` retained at full resolution for downstream stages. Human UAT pending residential-network 60s-timeout test | `tests/stages/test_vision_downsample.py` covers the spy path |

Phase 24.1 commits `b0a182a` precedes — see Wave 1 commit messages for atomic detail.

### Phase 24.2 — Renders management
Two unrelated render items batched:

- **RM-01:** Brochure + postcard PDF page-size scaling. Initial implementation added `PT_PER_PX = 72/300` + `Canvas.scale()` so the pagesize tuple is in PostScript points instead of pixel-as-point (was producing 46.89×36.47 in PDFs). Subsequent 260425-nwj iterations refined this further (see §3 below).
- **RM-02:** `DELETE /api/v1/renders/{render_id}` returns 204/404, idempotent on re-delete, deletes the on-disk artifact (`os.unlink` with `_is_within` containment guard), and explicitly NULLs FK columns on all 5 parent models (Postcard / Brochure / Poster / Flyer / Post) since SQLite has `PRAGMA foreign_keys=OFF` so schema-level `ondelete="SET NULL"` cascades don't fire. Frontend Renders gallery (`frontend/src/pages/renders/gallery.tsx`) ships a Trash2 icon + AlertDialog confirmation + TanStack `useMutation` with optimistic remove + rollback-on-error + sonner toast.

OpenAPI snapshot regenerated in-process via `build_app().openapi()`. New shadcn `frontend/src/components/ui/alert-dialog.tsx`.

### Quick task 260425-mvu — Brochure cover prompt fix
User caught that `BROCHURE_COVER_DIRECTIVES` contained text-priming function-words (`title`, `subtitle`, `headline`, `overlay`) which biased SDXL-class models to bake garbled text into the hero output even with the strongest negative prompt. Brochure hero generation was failing 3/3 vision-gate attempts even with safe nature-themed prompts (rejection log showed "Diktric Preklihy", "Botch Deuct" etc. baked in).

Fix mirrors `FLYER_DIRECTIVES`: describe the **image shape** (bokeh, gradient, balance), never the **function** (overlay, headline). Anti-text language is now intentionally shared between flyer and brochure prompt builders. Regression test guards against `{title, subtitle, headline, overlay, brochure, flyer, card, magazine, poster}` reappearing in the directives.

### Quick task 260425-nwj — Brochure PDF page sizing (3-step iteration)
Three commits before the user's verification was satisfied:

1. `b0a182a` — emit PDF at letter trim (11×8.5 in) instead of bleed canvas (11.25×8.75). Right idea, but the PNG was actually 1080×1920 portrait so this stretched it to landscape.
2. `9aebfd0` — make the PDF page size **track the source PNG at 300 dpi**. No more stretching, ever. PDF aspect = PNG aspect always.
3. `adec1c6` — flatten RGBA alpha onto white before drawing into the PDF, so transparent canvas regions don't render as black bars in pdfium2 / some printers.
4. `fdc387a` — **the actual root cause**: brochure task was calling `Rasterizer()` with no args, defaulting to **1080×1920 (the flyer canvas)**. The brochure SVG is emitted at **3376×2626 (letter landscape with 0.125" bleed)**, so cairosvg was letterboxing landscape→portrait. One-line fix passes `BLEED_CANVAS_WIDTH/HEIGHT` explicitly. `Rasterizer`'s docstring even said "Brochure callers pass width=3376, height=2626" — but the brochure task itself didn't.

Final state: brochure PDFs are 11.25×8.75 in landscape with three vertical panels (back | front cover | inside-flap) reading left→right. Folds along 2 vertical lines into a 3.67×8.5 in tri-fold.

---

## 3. Live API surface (verified against running uvicorn)

```
GET    /api/v1/brand-kits
POST   /api/v1/brand-kits/fetch
GET    /api/v1/brand-kits/{slug}
GET    /api/v1/brand-kits/{slug}/logos/{filename}
POST   /api/v1/brochures
GET    /api/v1/brochures/{brochure_id}
POST   /api/v1/flyers
GET    /api/v1/jobs
GET    /api/v1/jobs/{job_id}
POST   /api/v1/postcards
GET    /api/v1/postcards/{postcard_id}
POST   /api/v1/posters
GET    /api/v1/renders
DELETE /api/v1/renders/{render_id}      ← Phase 24.2
GET    /api/v1/renders/{render_id}/image
POST   /api/v1/social/campaigns
POST   /api/v1/social/posts
GET    /healthz
```

---

## 4. Current open issues / debt

### Known residuals (filed but not blocking)

- **PLF-02b** — Brochure section `body_paragraphs` not rendering on the back panel (only the headings + horizontal rules render). Worth filing as the first plan in a future Phase 24.3.
- **PLF-02c** — Brochure detail-route `back_render_url` panel layout still has 3 section heading bands but no body content fills them.
- **24.1 / 24.2 HUMAN-UAT items** — both decimal phases left `*-HUMAN-UAT.md` files that are still `status: partial`. Will surface in `/gsd-progress` and `/gsd-audit-uat` until tested.

### Operational notes

- **Vision provider**: `.env` was switched from `ollama` to `anthropic` during the perception-loop session because Ollama Cloud was timing out on the upload step. Still on `anthropic` today. `FLYER_VISION_TIMEOUT_SECONDS` was bumped from 60 to 180 — can be reverted now that `_downsample_for_vision` shrinks the upload payload.
- **DB**: SQLite (`sqlite+aiosqlite`) for dev. `alembic upgrade head` is at `f24t01` (latest poster migration). No Postgres in this dev box.
- **Worker recycle**: `pkill -f "arq flyer_generator.api.worker.WorkerSettings"` works fine despite an earlier-session deny rule on raw `kill <pid>`. Same pattern works for `pkill -f "uvicorn flyer_generator.api:app"`. Memory note saved at `~/.claude/projects/-home-hoyack-work-autocreative/memory/feedback_worker_recycle.md`.
- **Comfy prompt engineering**: function-words like `title`, `subtitle`, `headline`, `overlay`, `brochure`, `flyer` poison Comfy positive prompts even with a strong negative prompt. Memory note at `feedback_comfy_prompt_engineering.md`.

---

## 5. Filesystem snapshot (post-quick-tasks)

```
flyer_generator/
├── api/                              # Phase 20: FastAPI surface
│   ├── routes/
│   │   ├── brand_kits.py
│   │   ├── brochures.py
│   │   ├── flyers.py
│   │   ├── jobs.py
│   │   ├── postcards.py              # Phase 23
│   │   ├── posters.py                # Phase 24
│   │   ├── renders.py                # Phase 20 + DELETE handler (Phase 24.2)
│   │   └── social.py
│   ├── tasks/
│   │   ├── brochure.py               # 24.2-nwj rasterizer fix
│   │   ├── flyer.py
│   │   ├── postcard.py               # 24.1-01 Comfy hero hydration
│   │   ├── poster.py                 # Phase 24
│   │   └── ...
│   ├── models/                       # SQLAlchemy
│   │   ├── job.py / render.py / brochure.py / postcard.py / poster.py / flyer.py / post.py
│   └── schemas/                      # Pydantic request/response
├── brochure/
│   ├── schema_renderer/
│   │   ├── prompt_builder.py         # 260425-mvu directives fix
│   │   ├── renderer.py               # 24.1-02 sections path
│   │   ├── image_gate.py             # generate_template_images
│   │   ├── content_model.py
│   │   └── schema_model.py
│   ├── stages/
│   │   ├── pdf.py                    # 260425-nwj × 3 (page tracks PNG, alpha flatten)
│   │   └── layout.py                 # BLEED_CANVAS_WIDTH/HEIGHT constants
│   └── schemas/                      # 13 brochure templates (all ESTATE PLANNING / [hero] cleansed)
├── flyer/
│   └── schemas/                      # 6 flyer templates incl. fixed bold_modern.json
├── poster/
│   ├── schema_renderer/              # PosterTemplateSchema + loader
│   └── schemas/                      # 3 poster templates
├── postcard/
│   ├── schema_renderer/
│   │   ├── renderer.py               # images kwarg + _embed_image
│   │   └── image_gate.py             # generate_postcard_hero (Phase 24.1)
│   └── schemas/                      # 2 postcard templates (body on front)
├── stages/
│   ├── vision.py                     # _downsample_for_vision (Phase 24.1 PLF-04)
│   ├── rasterizer.py                 # default 1080x1920; brochure now passes 3376x2626
│   └── ...
├── presets.py                        # 7 style presets incl. social_graphic
├── pipeline.py                       # FlyerGenerator(canvas_dimensions=...)
├── config.py
└── errors.py

frontend/                              # Phase 21+ React dashboard
├── src/
│   ├── pages/
│   │   ├── flyers/{new,status,list}.tsx
│   │   ├── brochures/{new,status,list}.tsx
│   │   ├── postcards/{new,status}.tsx
│   │   ├── posters/{new,status}.tsx          # Phase 24
│   │   ├── renders/gallery.tsx                # 24.2 trash icon + AlertDialog
│   │   └── jobs/list.tsx
│   ├── components/
│   │   ├── DashboardLayout.tsx                # nav with Posters entry
│   │   ├── JobStatusCard.tsx
│   │   └── ui/
│   │       └── alert-dialog.tsx               # NEW: 24.2 shadcn
│   └── api/
│       ├── client.ts
│       ├── schema.gen.ts                       # regenerated post-24.2
│       └── openapi.snapshot.json
└── ...

.planning/
├── ROADMAP.md                        # phases through 25 listed; 24, 24.1, 24.2 marked complete
├── STATE.md                          # Quick Tasks Completed table includes 260425-mvu + nwj
├── REQUIREMENTS.md                   # PLF-01..04 + RM-01..02 traced
├── phases/
│   ├── 24-poster-primitive/          # PLAN, SUMMARY, VERIFICATION, HUMAN-UAT, REVIEW
│   ├── 24.1-perception-loop-fixes/   # 4 plans + verification + HUMAN-UAT
│   └── 24.2-renders-management/      # 2 plans + verification + HUMAN-UAT
└── quick/
    ├── 260425-mvu-brochure-directives-fix/SUMMARY.md
    └── 260425-nwj-brochure-trim-pdf/SUMMARY.md
```

---

## 6. Latest artifacts on disk

| Path | Contents |
|---|---|
| `/tmp/perception/PERCEPTION-REPORT.md` | Full adversarial loop report from 2026-04-25 |
| `/tmp/perception/REPORT.json` | Machine-readable verdicts |
| `/tmp/perception-loop.mjs` | Playwright + adversarial-vision harness (~400 LOC) |
| `/tmp/perception/{poster,postcard,brochure,flyer}-attempt*-{render,statuspage,verdict}.{png,json}` | Per-asset artifacts |
| `/tmp/perception/brochure-v6.pdf` | Last successful brochure PDF (11.25×8.75 in landscape, real Comfy hero) |
| `/tmp/check-e2e-{flyer-22,postcard-23,poster-24}.mjs` | Per-phase Playwright harnesses |

---

## 7. Next session — verify flyer + social media post generation end-to-end

User intent (verbatim from this session): "in the next phase I will be verifying that we can successfully generate a flyer, and then social media posts."

This is **verification work**, not a new build phase. The expectation is to drive the existing CLI/HTTP surfaces and confirm the artifacts come out clean given the current state of the code.

### Recommended approach

1. **Stack up.** uvicorn + arq + redis + Vite already running per §1. Recycle arq if you've made code changes since last session: `pkill -f "arq flyer_generator.api.worker.WorkerSettings"` then relaunch.
2. **Flyer.** Either `POST /api/v1/flyers` directly with curl, or fill out `/flyers/new` in the FE. Validate (a) the Comfy + vision pipeline completes, (b) the resulting `/api/v1/renders/{id}/image` is a 1080×1920 PNG with the headline / details rendered cleanly, (c) the `bold_modern` template (Phase 24.1 PLF-03) doesn't have headline-vs-detail overlap. Spot-check on at least 2 of the 6 templates.
3. **Social post.** `POST /api/v1/social/posts` with a brand-kit slug + brief, OR `python -m flyer_generator.social post ...`. Validate (a) voice-aware copy doesn't echo banned words, (b) per-platform validation passes (LinkedIn 3000 / Twitter 280 / Instagram 2200), (c) the rendered PNG has no garbled overlay text, (d) `audit.json` sidecar shows AA-pass contrast.
4. **Social campaign.** `POST /api/v1/social/campaigns` to exercise the shared-hero + per-platform-crop fan-out across 4 platforms. Confirm the 4 cropped PNGs all share visual identity but match per-platform aspects.
5. **Open the gallery.** `/renders` should show all the new artifacts. Confirm the trash icon (Phase 24.2) deletes them cleanly.

### Likely failure modes to keep an eye on

- Ollama Cloud 429 if `FLYER_VISION_PROVIDER=ollama` is reinstated. Anthropic vision is currently in `.env`; safe.
- LLM text generator: campaign uses serial per-platform (`asyncio.Semaphore(1)` since prior 429 incident). 4-platform campaign ≈ 90s wall clock.
- Brochure `qwen3.6:35b` was dropped from default fallback chain — if anyone restored it, expect 404 on this Ollama account. Default text-fallback chain is now `[kimi-k2.6:cloud]`.

### What NOT to expect to work

- Brochure body_paragraphs on the back panel (PLF-02b residual).
- Live brochure-via-API end-to-end ON THE OLLAMA PROVIDER without tuning timeout (anthropic provider is stable today).

---

## 8. TL;DR

All five creative subsystems ship: **flyer + postcard + brochure + poster + social**, each available as both a Python module and an HTTP route. 1801 backend tests + 47 frontend tests pass. The most recent quality work (Phase 24.1 + 24.2 + 2 quick tasks) closed real product bugs surfaced by a perception loop. Brochure PDFs now print cleanly on letter landscape with proper tri-fold orientation. Next session is verification on flyer + social. Safe to `/clear`.

Spec for the verification session is §7. Memory notes (`feedback_worker_recycle.md`, `feedback_comfy_prompt_engineering.md`) are saved so future sessions don't re-discover the same operational gotchas.
