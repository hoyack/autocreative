---
phase: 21-react-frontend-dashboard
reviewed: 2026-04-23T14:51:58Z
depth: standard
files_reviewed: 23
files_reviewed_list:
  - flyer_generator/api/routes/brand_kits.py
  - flyer_generator/api/routes/brochures.py
  - flyer_generator/api/routes/jobs.py
  - flyer_generator/api/routes/renders.py
  - flyer_generator/api/schemas/brochures.py
  - flyer_generator/api/schemas/jobs.py
  - flyer_generator/api/schemas/renders.py
  - flyer_generator/api/tasks/brochure.py
  - frontend/src/api/client.ts
  - frontend/src/hooks/useJob.ts
  - frontend/src/components/JobStatusCard.tsx
  - frontend/src/components/RenderPreview.tsx
  - frontend/src/components/LogoGallery.tsx
  - frontend/src/pages/brand-kits/new.tsx
  - frontend/src/pages/brand-kits/detail.tsx
  - frontend/src/pages/flyers/new.tsx
  - frontend/src/pages/brochures/new.tsx
  - frontend/src/pages/social/posts/new.tsx
  - frontend/src/pages/social/campaigns/new.tsx
  - frontend/src/pages/jobs/list.tsx
  - frontend/src/pages/renders/gallery.tsx
  - frontend/vitest.config.ts
  - frontend/vite.config.ts
findings:
  critical: 0
  warning: 4
  info: 9
  total: 13
status: issues_found
---

# Phase 21: Code Review Report

**Reviewed:** 2026-04-23T14:51:58Z
**Depth:** standard
**Files Reviewed:** 23
**Status:** issues_found

## Summary

Phase 21 ships the React/Vite dashboard plus four list-endpoint backend
additions (`GET /api/v1/brand-kits/{slug}/logos/{filename}`, `GET /api/v1/jobs`,
`GET /api/v1/renders`, `GET /api/v1/brochures/{id}`) and a new brochure worker
task. Overall security posture is strong: every identified attacker-reachable
path honors the T-1 containment guard (`_logo_is_within` / `_is_within`),
every user-submitted string is rendered through JSX text children (React
auto-escapes), every enum filter is Pydantic/zod-validated to block
SQL-smuggling, and `extra="forbid"` + zod `.strict()` are applied
consistently across request bodies. The scrape endpoint correctly delegates
SSRF gating to the existing `flyer_generator/brand_kit/scraper.py` guard.

Four warning-level issues need attention:

1. **Silent dropped field** in the brochure worker: `payload["workflow"]`
   from the POST body is never read — the task reads `payload["workflow_name"]`
   and falls back to `"turbo_landscape"`, so user-supplied workflow overrides
   are ignored.
2. **Double-counting in `list_brand_kits` pagination**: the filesystem fuse
   compares against only the current page's DB slugs, inflating `total` and
   duplicating rows across pages.
3. **Stale QUEUED job on enqueue failure**: `create_brand_kit_fetch` and
   `create_brochure` commit the JobRecord before calling `enqueue_job`; if
   enqueue raises, the row is orphaned in `queued` with no compensating
   transition.
4. **Fragile PDF URL detection** in `RenderPreview`: `lower.includes("/pdf")`
   would false-positive on any URL whose path contains `/pdf` as a
   substring (e.g. a ULID that begins with `pdf` in lowercased form, or any
   path segment containing "pdf"). Low probability today but a latent
   landmine.

Nine info-level items cover minor type-safety, filename UX, and consistency
nits. No critical-severity issues found.

## Warnings

### WR-01: Brochure worker ignores user-supplied `workflow` field

**File:** `flyer_generator/api/tasks/brochure.py:78`
**Issue:** `BrochureCreateRequest` (`flyer_generator/api/schemas/brochures.py:24`)
defines the field as `workflow: str = "turbo_landscape"`. The POST route
serializes the body via `body.model_dump(mode="json")` which produces the key
`"workflow"`. But the worker reads `payload.get("workflow_name", "turbo_landscape")`,
so any user-supplied override is silently dropped and the hard-coded default
is always used. The matching `style_preset` key is read correctly on line 79.
The comment on line 77 ("generate_template_images keyword is `workflow_name`,
NOT `workflow`") correctly describes the callee's kwarg, but missed that the
task itself must translate the payload key.
**Fix:**
```python
# flyer_generator/api/tasks/brochure.py:78
workflow_name=payload.get("workflow", "turbo_landscape"),
```
Also add a test that POSTs `{"workflow": "foo_portrait", ...}` and asserts
`generate_template_images` was called with `workflow_name="foo_portrait"`.

### WR-02: `list_brand_kits` FS-fuse over-counts across pages

**File:** `flyer_generator/api/routes/brand_kits.py:121-173`
**Issue:** `db_slugs` is built from *only the current page's* DB rows
(line 121). The filesystem fuse then appends any FS slug not in that set
(line 146). Concretely: if a slug exists in the DB on page 2, on page 1 the
code will not find it in `db_slugs` and will treat it as FS-only, inflating
`total` and producing a duplicate row (the same slug appears on page 1 via
FS and on page 2 via DB). Also, `total = db_total + fs_only_count` computes
`fs_only_count` from a single page's worth of FS iteration, so the reported
total is unstable across pages.
**Fix:** Load the FULL set of DB slugs (cheap — slug column only) before the
FS fuse, and compute `total` up front:
```python
# Full slug set for dedup (cheap — single indexed column scan):
all_db_slugs = {
    s for (s,) in (
        await session.execute(select(BrandKitRecord.slug))
    ).all()
}
...
# In the FS loop:
if slug in all_db_slugs:
    continue
# And for pagination correctness, compute fs-only count BEFORE pagination:
# (enumerate base_dir once to get the full fs_only list, then slice for the
#  current page window after merging with DB rows.)
```
If full-FS enumeration is too expensive, at minimum fix `total`: scan the
whole filesystem once to count FS-only slugs, and use that constant for
`total` on every page.

### WR-03: Orphan QUEUED job on `enqueue_job` failure

**File:** `flyer_generator/api/routes/brand_kits.py:66-83`,
`flyer_generator/api/routes/brochures.py:32-47`
**Issue:** Both creator routes commit the JobRecord (lines 77 / 40), THEN
call `arq_pool.enqueue_job`. If the arq pool is down, Redis is unavailable,
or `enqueue_job` raises for any other reason, the JobRecord sits in
`status=QUEUED` forever with no worker to advance it. The client gets a 500
(via FastAPI's error handlers), sees no `job_id`, and has no way to discover
the orphan — but the row still shows up in `GET /api/v1/jobs` and confuses
the dashboard. This is a data-integrity issue, not a security issue, but
it's a persistent failure mode worth fixing at the same time as the phase.
**Fix:** Wrap the enqueue in try/except and mark failed on error:
```python
# flyer_generator/api/routes/brand_kits.py (same pattern for brochures.py)
await session.commit()
try:
    await request.app.state.arq_pool.enqueue_job(
        "task_fetch_brand_kit",
        job_id=job_id,
        payload={"url": str(body.url), "slug": body.slug},
    )
except Exception:
    # Flip the just-created row to failed so the list view + detail page
    # reflect reality. Re-raise so the client sees a 500.
    async with request.app.state.sessionmaker() as s2:
        row = await s2.get(JobRecord, job_id)
        if row is not None:
            row.status = JobStatus.FAILED
            row.error_detail = {"reason": "enqueue_failed"}
            await s2.commit()
    raise
return JobCreated(job_id=job_id)
```

### WR-04: `RenderPreview` PDF detection false-positives on `/pdf` substring

**File:** `frontend/src/components/RenderPreview.tsx:17-23`
**Issue:**
```ts
if (lower.endsWith(".pdf") || lower.includes(".pdf?") || lower.includes("/pdf")) {
```
`lower.includes("/pdf")` will match any URL with `/pdf` as a substring in
the path — e.g. `/api/v1/renders/{id}/image` where `{id}` begins with
`pdf...` (26-char lowercased ULID beginning with "pdf"). A ULID starting
with the 3-char sequence `01H` is the current 2026 epoch prefix so
collisions are unlikely today, but the check is fragile as soon as the
URL scheme changes. `gallery.tsx` already works around this by branching
on `RenderRecord.kind` (`isPdfKind`) — the component itself should be made
robust. Two options:
**Fix option A (explicit prop, preferred):** add a `kind` or `contentType`
prop and rely on it; callers pass through render kind so the decision is
never based on URL parsing:
```tsx
interface RenderPreviewProps {
  url: string;
  alt?: string;
  className?: string;
  isPdf?: boolean; // explicit, callers know their content type
}
// ...
if (isPdf || lower.endsWith(".pdf") || lower.includes(".pdf?")) { ... }
```
**Fix option B (tighter URL regex):**
```ts
// Match .pdf extension ONLY (not substring). No /pdf fallback.
const isPdf = /\.pdf($|\?)/i.test(url);
```
Drop the `/pdf` substring check entirely; `gallery.tsx` is already driving
PDF rendering off `kind`.

## Info

### IN-01: `RenderPreview` filename for downloads is the ULID, not `render.pdf`

**File:** `frontend/src/components/RenderPreview.tsx:24-25`
**Issue:** `url.split("/").filter(Boolean).slice(-2, -1)[0] ?? "render.pdf"`
on the URL `/api/v1/renders/<ulid>/image` returns `<ulid>` (never undefined),
so the `?? "render.pdf"` branch never fires and the suggested filename is
the bare 26-char ULID with no `.pdf` extension — making the OS Save dialog
default to no extension. Consider: `` `${ulid}.pdf` ``.

### IN-02: `list_renders` accepts untyped `kind` string (no enum validation)

**File:** `flyer_generator/api/routes/renders.py:132`
**Issue:** `kind: str | None = Query(default=None, max_length=40)`.
Sibling endpoint `list_jobs` validates `kind: JobKind | None` which
generates a 422 on unknown kinds. `list_renders` just returns an empty
list. Not a security issue (SQLAlchemy parameterizes), but an inconsistency
the FE dropdown silently hides. Consider a `RenderKind` StrEnum in
`api/models/render.py` and use `RenderKind | None` here.

### IN-03: `list_brand_kits` FS-fuse items appear in append order, not `scraped_at` order

**File:** `flyer_generator/api/routes/brand_kits.py:140-167`
**Issue:** DB rows are `order_by(BrandKitRecord.scraped_at.desc())`, then FS
rows are appended in `sorted(base_dir.iterdir())` order (alphabetic by
slug). The merged `items` list is never re-sorted. FS-only entries always
appear at the tail regardless of recency. After WR-02 is fixed, this
should be addressed at the same time by sorting the merged list:
```python
items.sort(key=lambda s: s.scraped_at, reverse=True)
```

### IN-04: `useJob` swallows the underlying error message

**File:** `frontend/src/hooks/useJob.ts:19`
**Issue:** `throw new Error("failed to fetch job")` loses the
`ApiErrorBody.detail` string returned by FastAPI (trace_id + error_type
also lost). Callers display `(error as Error).message` and users see a
generic message instead of (e.g.) "job not found" or an LLM-retry summary.
**Fix:**
```ts
if (error || !data) {
  const e = error as ApiErrorBody | undefined;
  const msg = typeof e?.detail === "string" ? e.detail : "failed to fetch job";
  throw new Error(msg);
}
```

### IN-05: `JobStatusCard` effect uses `job?.status` only but closes over `job`

**File:** `frontend/src/components/JobStatusCard.tsx:42-46`
**Issue:** `useEffect(..., [job?.status])` references `job` in the guard
but deps only on `job?.status`. React Hooks' exhaustive-deps rule would
flag this (correct runtime behavior today since the callback only uses
`setNow(Date.now())`, but one future refactor that reads from `job` inside
the interval would introduce a stale-closure bug). Recommend either adding
`job` to the deps array or destructuring: `const status = job?.status; ...
[status]`.

### IN-06: `brochures/new.tsx` parses the content JSON twice

**File:** `frontend/src/pages/brochures/new.tsx:57-66, 123`
**Issue:** `zod.refine` calls `JSON.parse(s)` and discards the result; then
`mutationFn` re-parses on submit. A tiny performance issue on big pastes,
but also means error messages only mention "must be valid JSON" and not
the underlying position/property. Consider a `z.string().transform(...)`
that parses once and puts the parsed object on the form state.

### IN-07: `JobsListPage` filter `<label>` not associated with `<Select>`

**File:** `frontend/src/pages/jobs/list.tsx:116-158`
**Issue:** Bare `<label className="text-muted-foreground text-xs">Kind</label>`
has no `htmlFor` attribute and no nested control. Screen readers won't
associate the label with the Select. Consider wrapping with `<label>` that
contains the Select, or use the ShadCN `<Label htmlFor="...">`. Same
finding applies to `renders/gallery.tsx:89-97`.

### IN-08: `task_generate_brochure` `getattr(content, "title", template_name)` fallback is dead code

**File:** `flyer_generator/api/tasks/brochure.py:130`
**Issue:** `BrochureContent.title` is a required field (Pydantic would have
raised at `model_validate` on line 57 if missing), so `getattr(..., template_name)`
can never return the fallback. Not a bug — just misleading. Replace with
`content.title` to document intent and let pyright catch any future
schema change.

### IN-09: `brochure.py` hard-coded `logo_bytes = None` leaves logos unrendered

**File:** `flyer_generator/api/tasks/brochure.py:87-94`
**Issue:** The comment acknowledges this as a known gap
("When logo-byte hydration lands, replace with the correct load"), but
it's worth tracking as a visible TODO so the dashboard's brand-kit-selector
UX doesn't silently produce logo-less brochures. Suggest adding a
`structlog` warning when `slug` is provided but no logo bytes are hydrated:
```python
if slug is not None:
    log.warning(
        "brochure_logo_not_hydrated",
        slug=slug,
        reason="logo_bytes loader not yet implemented",
    )
```

---

_Reviewed: 2026-04-23T14:51:58Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
