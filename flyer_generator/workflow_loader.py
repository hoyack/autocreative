"""Load ComfyUI workflow configurations from JSON files."""

from __future__ import annotations

import json
from pathlib import Path

from flyer_generator.models import WorkflowConfig

_WORKFLOWS_DIR = Path(__file__).parent / "workflows"


def load_workflow(name_or_path: str) -> WorkflowConfig:
    """Load a workflow configuration by name or file path.

    If name_or_path ends with '.json', treat as a file path.
    Otherwise, look up in the built-in workflows directory.

    Returns:
        WorkflowConfig with metadata and node graph ready for injection.

    Raises:
        FileNotFoundError: If the workflow file does not exist.
        ValueError: If injection points reference missing node IDs.
    """
    if name_or_path.endswith(".json"):
        path = Path(name_or_path)
    else:
        path = _WORKFLOWS_DIR / f"{name_or_path}.json"

    if not path.exists():
        available = list_workflows()
        raise FileNotFoundError(
            f"Workflow not found: {path}. Available: {available}"
        )

    raw = json.loads(path.read_text(encoding="utf-8"))

    meta = raw.pop("_flyer_meta")
    workflow_dict = raw  # remaining keys are the ComfyUI node graph

    # Validate injection points reference existing nodes
    for role, node_id in meta["injection_points"].items():
        if node_id not in workflow_dict:
            raise ValueError(
                f"Injection point '{role}' references node '{node_id}' "
                f"which does not exist in workflow '{meta['name']}'. "
                f"Available nodes: {list(workflow_dict.keys())}"
            )

    return WorkflowConfig(
        name=meta["name"],
        description=meta.get("description", ""),
        latent_dimensions=tuple(meta["latent_dimensions"]),
        injection_points=meta["injection_points"],
        workflow=workflow_dict,
    )


def list_workflows() -> list[str]:
    """List available built-in workflow names."""
    return sorted(
        p.stem for p in _WORKFLOWS_DIR.glob("*.json")
    )
