web: uv run uvicorn flyer_generator.api:app --reload --host 0.0.0.0 --port 8000
worker: uv run arq flyer_generator.api.worker.WorkerSettings
