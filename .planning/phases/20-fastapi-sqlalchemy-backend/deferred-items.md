# Phase 20 — Deferred Items

Out-of-scope discoveries logged during plan execution. These are pre-existing
issues NOT caused by the current plan's changes.

## Pre-existing CSV-env-var bug in `flyer_generator/config.py`

**Discovered during:** Plan 20-02 execution (2026-04-22)

**Symptom:** The existing `Settings` fields `ollama_text_model_fallbacks` and
`ollama_vision_model_fallbacks` are declared as `list[str]` with
`Field(default_factory=lambda: ["kimi-k2.6:cloud"])` and are documented (in
both `CLAUDE.md` "LLM Resilience" section and the class docstring) to accept
a comma-separated env var like `FLYER_OLLAMA_TEXT_MODEL_FALLBACKS="kimi-k2.6:cloud,qwen3.6:35b"`.

In the installed `pydantic-settings==2.13.1`, a bare `list[str]` field is
treated as a **complex** type and parsed as JSON. `"kimi-k2.6:cloud,qwen3.6:35b"`
is not valid JSON, so setting the env var raises
`pydantic_settings.exceptions.SettingsError: error parsing value for field
"ollama_text_model_fallbacks" from source "EnvSettingsSource"` at
`Settings()` instantiation.

Verified:

```bash
FLYER_OLLAMA_TEXT_MODEL_FALLBACKS="a,b,c" python -c "from flyer_generator.config import Settings; Settings()"
# -> SettingsError
```

**Why deferred:** Plan 20-02's scope is `flyer_generator/api/__init__.py` and
`flyer_generator/api/config.py`. Editing `flyer_generator/config.py` to add a
validator is out of scope for this plan. The bug exists on `master` today.

**Workaround applied in 20-02:** `AppSettings.cors_origins` uses an explicit
field-level `@field_validator(..., mode="before")` to accept CSV input, so
Plan 20-02's own must_haves (`FLYER_CORS_ORIGINS="http://a,http://b"` →
`['http://a','http://b']`) hold. The pre-existing `ollama_*_fallbacks` fields
remain broken on `master` and in every derived `AppSettings` instance.

**Suggested follow-up plan:** A small patch to `flyer_generator/config.py`
adding a shared `@field_validator("ollama_text_model_fallbacks",
"ollama_vision_model_fallbacks", mode="before")` that splits bare strings on
commas. Would restore the behavior claimed in `CLAUDE.md`'s "LLM Resilience"
table. Not urgent because the defaults are correct and only users setting the
env var hit the bug.
