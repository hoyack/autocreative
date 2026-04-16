# Domain Pitfalls

**Domain:** AI-powered flyer generation (ComfyUI + Claude vision + SVG composition + cairosvg rasterization)
**Researched:** 2026-04-16

## Critical Pitfalls

Mistakes that cause rewrites, broken output, or silent corruption.

### Pitfall 1: CairoSVG Silently Drops Base64-Embedded Images Without `unsafe=True`

**What goes wrong:** CairoSVG 2.7.0 introduced a security fix (CVE-2023-27586) that blocks external file loading. As a side effect, `data:image/png;base64,...` URIs in `<image>` elements are silently ignored -- the SVG renders with no background image and no error raised. Version 2.7.1 fixed this for data URIs specifically, but pinning to the wrong version or running on a system package manager that ships 2.7.0 produces blank backgrounds.

**Why it happens:** The security fix treated data URIs as external resources. The distinction between embedded data URIs and truly external `file://` or `http://` URIs was not preserved.

**Consequences:** Output PNGs contain text overlays floating on a transparent or white background. The pipeline reports success because cairosvg returns valid PNG bytes at the correct dimensions. The sanity check (assert 1080x1920) passes. Users only discover the problem visually.

**Prevention:**
- Pin `cairosvg>=2.7.1` in requirements. Add a version check at import time.
- Add a visual regression test: rasterize a known SVG with a base64 image, verify the output PNG is not mostly white/transparent (check average pixel luminance or a known pixel coordinate).
- If forced to use 2.7.0: pass `unsafe=True` to `svg2png()`, but document the security tradeoff.
- Maintain resvg-py as a tested fallback -- switch if cairosvg output is blank.

**Detection:** Average pixel value of output PNG is near 255 (white) or 0 (transparent). A simple smoke test catches this instantly.

**Phase:** Rasterizer implementation (earliest testable stage). Must be validated before any integration testing.

**Confidence:** HIGH -- documented in [CairoSVG issue #383](https://github.com/Kozea/CairoSVG/issues/383) and [Debian bug #1050643](https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=1050643).

---

### Pitfall 2: CairoSVG Font Fallback Fails Silently on Linux Servers

**What goes wrong:** CairoSVG delegates font resolution to Cairo/FreeType/Fontconfig. When the SVG specifies `font-family="Arial, Helvetica, sans-serif"` and none of these fonts are installed (common on minimal Docker images and CI runners), Cairo silently substitutes a default font. The substituted font has different metrics -- text overflows containers, wraps at wrong positions, or renders at visually wrong sizes.

**Why it happens:** Fontconfig's alias chain (`Arial` -> `Helvetica` -> `Liberation Sans` -> `DejaVu Sans`) only works when the alias targets are installed. Minimal Linux images often have only `DejaVu Sans` or nothing. CairoSVG does not warn when a font family is unavailable.

**Consequences:** Text layout breaks. Title text wraps differently than designed. Fee badge pill shape is too narrow or too wide. The output is technically valid but looks broken. Worse: it works on dev machines (macOS/Windows with Arial installed) but fails in production Docker containers.

**Prevention:**
- Dockerfile must install `fonts-liberation` or `ttf-mscorefonts-installer` (for Arial). Pin this as a documented system dependency.
- Add a font availability check at startup: use `fc-list` or fontconfig bindings to verify Arial/Helvetica/Liberation Sans is present. Fail fast with a clear error, not silent degradation.
- Consider bundling Liberation Sans (Apache 2.0 licensed, metric-compatible with Arial) in the package and loading it explicitly.
- resvg-py alternative: resvg allows loading fonts from a specific directory path, avoiding system fontconfig entirely. This is a significant advantage for containerized deployments.

**Detection:** Compare rendered text bounding box width against expected width for a known string. Or: check `fc-list | grep -i arial` in a startup health check.

**Phase:** Rasterizer implementation + Docker/deployment setup. Must be validated in CI environment, not just dev machines.

**Confidence:** HIGH -- documented in [CairoSVG issue #273](https://github.com/Kozea/CairoSVG/issues/273), [#324](https://github.com/Kozea/CairoSVG/issues/324), and [#49](https://github.com/Kozea/CairoSVG/issues/49).

---

### Pitfall 3: Claude Vision JSON Parsing Relies on Fragile String Extraction

**What goes wrong:** The spec describes parsing Claude's response by stripping markdown fences and extracting between first `{` and last `}`. This works 95% of the time but breaks when: (a) Claude includes JSON examples or nested objects in prose before the actual response, (b) the response is truncated due to `max_tokens` limit, producing invalid JSON, (c) Claude returns a safety refusal instead of JSON.

**Why it happens:** Without structured outputs, Claude's response format is a best-effort convention, not a contract. The model can and does add preambles, use different fence styles, or restructure output across versions.

**Consequences:** `VisionResponseParseError` on valid images. The retry logic sends the same image again with "Return valid JSON only" -- but if the root cause is truncation or safety refusal, the retry also fails. Two wasted API calls + the image gets rejected even though it was fine.

**Prevention:**
- **Use Claude structured outputs (constrained decoding) instead of text parsing.** This is now GA for Claude Sonnet 4.5 and later. Set `response_format={"type": "json_schema", "json_schema": {...}}` in the API call. This compiles your schema into a grammar and guarantees valid JSON. The `VisionVerdict` Pydantic model can be converted to a JSON schema directly.
- If structured outputs are unavailable for the chosen model: use `tool_use` with `strict: true` as a fallback -- define a tool whose input schema matches `VisionVerdict`, and Claude will call it with validated JSON.
- Set `max_tokens` high enough to never truncate the response. The vision verdict JSON is ~300 tokens max; set `vision_max_tokens: 1024` (already in spec) but validate that the response `stop_reason` is `end_turn`, not `max_tokens`.
- Detect safety refusals by checking for `stop_reason: "end_turn"` with no JSON content, and surface a specific error ("Vision model refused to analyze this image") rather than a parse error.

**Detection:** Monitor `stop_reason` on every API response. Log the raw response on parse failure for debugging.

**Phase:** Vision evaluator implementation. This is a design decision that should be made before writing the parser.

**Confidence:** HIGH -- Claude structured outputs are [documented](https://docs.claude.com/en/docs/build-with-claude/structured-outputs) and GA. The fragile-parsing risks are well-known from the [Anthropic cookbook](https://github.com/anthropics/anthropic-cookbook/blob/main/tool_use/extracting_structured_json.ipynb).

---

### Pitfall 4: SVG Text Content Not XML-Escaped Causes Silent Render Corruption

**What goes wrong:** Event titles, venue names, and org names containing `&`, `<`, `>`, or `"` break the SVG XML structure. An event titled "Tom & Jerry's Fun Day" produces `<text>Tom & Jerry's Fun Day</text>` -- the `&` is an invalid XML entity start, causing the SVG parser to either reject the document or silently truncate text at that character.

**Why it happens:** SVG is XML. User-supplied strings inserted via f-strings or template concatenation bypass XML escaping. The spec correctly identifies `xml.sax.saxutils.escape()` as the solution, but this is easy to forget for one field (especially `url` or `fees`) or to apply inconsistently.

**Consequences:** cairosvg raises a cryptic `lxml.etree.XMLSyntaxError` or, worse, silently renders truncated text. The `&` in "Tom & Jerry" becomes "Tom " with everything after dropped. No clear error message pointing to the user's input.

**Prevention:**
- Create a single `escape_text(s: str) -> str` utility that wraps `xml.sax.saxutils.escape()` and call it on EVERY user-supplied string at the SVG composition boundary. Do not escape earlier (it would double-escape) or later (the SVG string is already built).
- Add a test case for every `EventInput` field containing `&`, `<`, `>`, `"`, and `'`. Include a fixture event with all special characters in the title.
- Consider using an XML builder (e.g., `lxml.etree.SubElement`) instead of f-strings to make escaping automatic. The spec recommends against Jinja2 but an XML builder is lighter and safer.
- Add a post-build validation step: parse the SVG string with `lxml.etree.fromstring()` before passing to cairosvg. This catches malformed XML early with a clear error.

**Detection:** The SVG fails to parse, or text is visually truncated. A unit test with `&` in the title catches this immediately.

**Phase:** SVG composer implementation. Must be enforced from the first line of SVG-building code.

**Confidence:** HIGH -- standard XML escaping issue, universally documented.

---

## Moderate Pitfalls

### Pitfall 5: ComfyCloud Polling Timeout With No Diagnostic Information

**What goes wrong:** The polling loop hits `poll_max_attempts` (default 20 * 4s = ~80s after initial 3s wait) and raises `ComfyJobTimeoutError`. But the error carries no information about whether the job is still running (and would succeed with more time), genuinely stuck, or failed silently on the ComfyCloud side.

**Why it happens:** ComfyCloud's status endpoint returns coarse states (`pending`, `running`, `completed`, `failed`). There is no progress percentage or estimated time remaining. Image generation time varies significantly with model and queue depth -- a busy queue might take 120s for a job that normally takes 30s.

**Prevention:**
- Log every poll response including the raw status string and any additional metadata.
- Include the last-seen status in `ComfyJobTimeoutError` so the caller knows "timed out while still `running`" vs "timed out while still `pending`" (stuck in queue vs slow generation).
- Make poll settings configurable (already in spec) but set defaults conservatively: 30 max attempts instead of 20 for production, with shorter intervals for tests.
- Implement exponential backoff for the polling interval (start at 2s, grow to 8s) rather than fixed intervals. This reduces API load on ComfyCloud during long generations.
- Surface ComfyCloud's queue position if available in the status response.

**Detection:** `ComfyJobTimeoutError` in production logs. Alert if timeout rate exceeds 5% of jobs.

**Phase:** ComfyClient implementation.

**Confidence:** MEDIUM -- based on general ComfyUI API behavior documented in [issue #4855](https://github.com/comfyanonymous/ComfyUI/issues/4855) and [RunComfy error docs](https://docs.runcomfy.com/serverless/error-codes).

---

### Pitfall 6: ComfyCloud 5xx Retries Without Idempotency Guards

**What goes wrong:** The spec calls for exponential backoff on 5xx responses. If the 5xx occurs on the `submit` endpoint, the retry submits the workflow again. ComfyCloud may have received and queued the first submission before returning a 5xx (e.g., gateway timeout after the backend accepted the job). Now two identical jobs are running, consuming API credits and potentially causing confusion if both complete.

**Why it happens:** The `submit` endpoint is not idempotent. A `POST` that times out at the HTTP layer may have succeeded server-side.

**Prevention:**
- After a 5xx on `submit`, check the status endpoint with the expected `prompt_id` before retrying. If the job exists and is `pending`/`running`, do not resubmit.
- Include a client-generated idempotency key in the request if ComfyCloud supports it (check API docs).
- Track all submitted `prompt_id` values and clean up (cancel) duplicate jobs if detected.
- Set HTTP timeouts (connect + read) separately: short connect timeout (5s), longer read timeout (30s) for the submit call.

**Detection:** Multiple jobs with identical seeds/prompts in ComfyCloud history. Unexpectedly high API credit usage.

**Phase:** ComfyClient implementation.

**Confidence:** MEDIUM -- standard distributed systems concern; ComfyCloud-specific idempotency behavior not verified.

---

### Pitfall 7: Vision Evaluation Rejects Good Images Due to Overly Strict Confidence Threshold

**What goes wrong:** The confidence threshold (default 0.6) flips `approved=True` to `False` when vision confidence is below the threshold. With artistic/abstract styles (watercolor, anime), Claude may return lower confidence scores even for perfectly suitable backgrounds, because the vision prompt was designed with photorealistic images in mind. This causes unnecessary regeneration loops, wasting time and API credits.

**Why it happens:** Confidence calibration varies across image styles. A photorealistic park scene gets 0.85 confidence; a watercolor interpretation of the same scene gets 0.55 because Claude is less certain about text placement zones on abstract imagery.

**Prevention:**
- Make the confidence threshold per-preset, not global. Artistic presets get lower thresholds (0.4-0.5), photorealistic gets 0.6+.
- Log confidence scores across all attempts during development to calibrate thresholds empirically before setting defaults.
- Include the preset style name in the vision prompt so Claude can calibrate its confidence expectations.
- Track the average number of attempts per preset. If a preset consistently requires 3 attempts, the threshold is too high for that style.

**Detection:** Average attempts-per-flyer exceeding 2.0 for a specific preset. Confidence scores clustering just below the threshold.

**Phase:** Vision evaluator tuning, after initial integration is working.

**Confidence:** MEDIUM -- inference based on LLM confidence behavior; needs empirical validation with real images.

---

### Pitfall 8: Base64-Encoded Background Makes SVG String Exceed Memory Expectations

**What goes wrong:** A 1080x1920 PNG is typically 1-4 MB. Base64 encoding inflates this by ~33%, producing a 1.3-5.3 MB data URI. The full SVG string with all text elements and scrims can reach 6+ MB. This is fine for a single flyer, but if the pipeline is later used in batch mode or if the SVG string is logged/serialized inadvertently, memory usage spikes.

**Why it happens:** The spec acknowledges the large SVG is transient. But developers adding logging, error reporting, or intermediate serialization may capture the full SVG string, multiplying the memory cost.

**Prevention:**
- Never log the full SVG string. Log a truncated version (first 200 chars + length) or log only metadata (dimensions, number of text elements, background size).
- In the `VisionVerdict` model, `raw_response` is already truncated to 500 chars. Apply the same discipline everywhere.
- If batch mode is added later, process flyers sequentially and release the SVG string immediately after rasterization (do not accumulate).
- Consider using a temporary file instead of an in-memory string for the SVG if memory constraints become an issue.

**Detection:** Memory profiling during batch runs. Log warnings if SVG string exceeds 5 MB.

**Phase:** SVG composer + pipeline orchestration. Awareness from the start, enforcement when batch mode is added.

**Confidence:** HIGH -- arithmetic fact about base64 encoding size.

---

### Pitfall 9: ComfyCloud Download Returns No Images or Wrong Image Format

**What goes wrong:** The `download_result` method uses `/api/history_v2/{prompt_id}` to locate the output filename, then `/api/view` to download. If the workflow output node is misconfigured, the history response may contain no output files, or the file may be JPEG instead of PNG (depending on the Save Image node configuration).

**Why it happens:** ComfyCloud workflows can have multiple output nodes or be configured to save in different formats. The workflow JSON from the n8n migration must exactly match the expected output configuration. A subtle change in the workflow (wrong node connection, different Save Image settings) silently changes the output format or location.

**Prevention:**
- Validate the downloaded bytes: check the PNG magic number (`\x89PNG\r\n\x1a\n`) before proceeding. Raise `InvalidImageFormatError` if not PNG.
- Validate image dimensions with Pillow immediately after download, before the upscale step.
- Store the exact ComfyCloud workflow JSON as a versioned fixture. Hash it and compare at runtime to detect accidental drift.
- Handle the "no outputs" case explicitly with a clear error message referencing the workflow configuration, not a generic IndexError.

**Detection:** `IndexError` when accessing the first image from the history response. Image header bytes not matching PNG signature.

**Phase:** ComfyClient implementation.

**Confidence:** MEDIUM -- based on typical ComfyUI API behavior; exact ComfyCloud API response format should be verified during implementation.

---

## Minor Pitfalls

### Pitfall 10: Title Auto-Sizing Widow Line Merge Creates Unexpected Layout

**What goes wrong:** The widow-line merge (if last wrapped line is <40% of previous, merge back) can produce a single very long line that overflows the SVG viewBox or overlaps other elements. Example: a title that wraps to 3 lines where line 3 is short -- merging it back makes line 2 very long.

**Prevention:**
- After merging, re-check that no line exceeds the maximum allowed width for the zone. If it does, undo the merge.
- Add test cases with titles at various lengths (short, medium, long, maximum 120 chars) to verify wrapping behavior.

**Phase:** SVG composer text layout.

**Confidence:** MEDIUM -- common text-layout concern.

---

### Pitfall 11: httpx AsyncClient Lifecycle Management

**What goes wrong:** Creating a new `httpx.AsyncClient` per request instead of sharing one across the pipeline prevents connection pooling and can leak connections. Conversely, sharing a client without proper cleanup leaves connections open.

**Prevention:**
- Create one `AsyncClient` in `FlyerGenerator.__init__` (or accept an injected one, as spec describes).
- Use `async with` context manager in the top-level entry point to ensure cleanup.
- Set explicit timeouts on the client (connect=5s, read=60s, pool=5s) rather than relying on defaults.

**Phase:** Pipeline orchestration setup.

**Confidence:** HIGH -- standard httpx best practice.

---

### Pitfall 12: Structured Output Schema Drift Between Pydantic Model and API Call

**What goes wrong:** If using Claude structured outputs, the JSON schema passed to the API must exactly match the Pydantic model used for deserialization. If a developer adds a field to `VisionVerdict` but forgets to update the API schema (or vice versa), the response either fails validation or silently drops fields.

**Prevention:**
- Generate the JSON schema from the Pydantic model at runtime using `VisionVerdict.model_json_schema()`. Do not maintain a separate hand-written schema.
- Add a test that compares the schema sent to Claude against the Pydantic model's generated schema.

**Phase:** Vision evaluator implementation.

**Confidence:** HIGH -- standard Pydantic v2 capability.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| ComfyClient (API integration) | Polling timeout without diagnostics; duplicate submissions on 5xx retry; wrong image format from workflow | Log every poll status; check for existing job before retry; validate PNG header on download |
| Vision evaluator (Claude API) | Fragile JSON parsing; truncated responses; safety refusals mistaken for parse errors; confidence threshold too strict for artistic styles | Use structured outputs or strict tool_use; check stop_reason; per-preset thresholds |
| SVG composer (text + scrim layout) | Unescaped XML characters in user text; widow merge overflow; base64 string bloating logs/memory | Centralized escape utility; post-merge width check; never log full SVG |
| Rasterizer (cairosvg/resvg) | Silent image drop on wrong cairosvg version; font substitution on Linux servers | Pin cairosvg>=2.7.1; install fonts in Docker; startup font check; resvg-py as tested fallback |
| Pipeline orchestration | httpx client lifecycle; excessive regen loops on artistic presets; no trace ID correlation in error paths | Shared client with cleanup; per-preset attempt budgets; bind trace_id at pipeline entry |
| Deployment / Docker | Missing system deps (cairo, libffi, fonts); cairosvg version mismatch in system packages | Explicit Dockerfile with all deps; smoke test in CI that rasterizes a known SVG |

## Sources

- [CairoSVG issue #383: data URI broken without unsafe flag](https://github.com/Kozea/CairoSVG/issues/383)
- [CairoSVG issue #273: font-family not supported](https://github.com/Kozea/CairoSVG/issues/273)
- [CairoSVG issue #324: custom fonts problem](https://github.com/Kozea/CairoSVG/issues/324)
- [CairoSVG documentation](https://cairosvg.org/documentation/)
- [Claude structured outputs documentation](https://docs.claude.com/en/docs/build-with-claude/structured-outputs)
- [Anthropic cookbook: extracting structured JSON](https://github.com/anthropics/anthropic-cookbook/blob/main/tool_use/extracting_structured_json.ipynb)
- [ComfyUI API polling issue #4855](https://github.com/comfyanonymous/ComfyUI/issues/4855)
- [RunComfy API error codes](https://docs.runcomfy.com/serverless/error-codes)
- [ComfyUI Cloud API reference](https://docs.comfy.org/development/cloud/api-reference)
- [resvg-py font documentation](https://resvg-py.readthedocs.io/en/latest/font.html)
- [Debian bug #1050643: cairosvg data URI regression](https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=1050643)
