import json
import random
from pathlib import Path

from app.config import settings


class ModelNotFoundError(Exception):
    """Raised when a requested model is not registered."""


class InvalidSizeError(Exception):
    """Raised when the requested size is not supported by a model."""


class WorkflowAdapter:
    """
    Boundary between OpenAI request semantics and ComfyUI API workflow JSON.

    This is the ONLY place that knows about node IDs.
    """

    def __init__(self, workflow_path: str, node_map: dict):
        self.workflow_path = Path(workflow_path)
        self.node_map = node_map

    def build(
        self,
        prompt: str,
        width: int | None = None,
        height: int | None = None,
        seed: int | None = None,
        n: int = 1,
        negative_prompt: str | None = None,
        steps: int | None = None,
        cfg: float | None = None,
        input_image: str | None = None,
    ) -> dict:
        workflow = self._load()

        # Positive prompt
        workflow[self.node_map["prompt"]]["inputs"]["text"] = prompt

        # Negative prompt (if the node exists in this workflow)
        if neg_node := self.node_map.get("negative_prompt"):
            workflow[neg_node]["inputs"]["text"] = negative_prompt or ""

        # Width / height (optional; some workflows derive size from the input image)
        if width is not None and (width_node := self.node_map.get("width")):
            workflow[width_node]["inputs"]["value"] = width
        if height is not None and (height_node := self.node_map.get("height")):
            workflow[height_node]["inputs"]["value"] = height

        # Input / reference image (img2img): LoadImage node expects its "image" input
        if input_image is not None and (img_node := self.node_map.get("input_image")):
            workflow[img_node]["inputs"]["image"] = input_image

        # Batch size
        workflow[self.node_map["latent"]]["inputs"]["batch_size"] = n

        # Seed
        if seed is None:
            seed = random.randint(0, 2**53 - 1)
        workflow[self.node_map["seed"]]["inputs"]["noise_seed"] = seed

        # Steps / CFG (optional overrides)
        if steps is not None and (step_node := self.node_map.get("steps")):
            workflow[step_node]["inputs"]["steps"] = steps
        if cfg is not None and (cfg_node := self.node_map.get("cfg")):
            workflow[cfg_node]["inputs"]["cfg"] = cfg

        return workflow

    def _load(self) -> dict:
        if not self.workflow_path.exists():
            raise ModelNotFoundError(
                f"Workflow file not found: {self.workflow_path}"
            )
        return json.loads(self.workflow_path.read_text(encoding="utf-8"))


# --- Model registry -----------------------------------------------------------

def load_models(registry_path: str | None = None) -> dict:
    """Load the model registry from the configured JSON file.

    The registry file maps model names to their workflow path, node map,
    supported sizes, and ownership. It lives outside the codebase so users
    can register new workflows without changing code.
    """
    path = Path(registry_path or settings.workflow_registry)
    if not path.exists():
        raise ModelNotFoundError(
            f"Model registry file not found: {path}. "
            "See workflows/README.md for setup instructions."
        )
    registry = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(registry, dict):
        raise ModelNotFoundError(
            f"Model registry file must contain a JSON object: {path}"
        )
    return registry


def get_adapter(model: str) -> tuple[WorkflowAdapter, dict]:
    """Return the WorkflowAdapter and its model metadata for a model name."""
    entry = load_models().get(model)
    if entry is None:
        raise ModelNotFoundError(f"Unknown model: {model}")
    adapter = WorkflowAdapter(entry["workflow"], entry["nodes"])
    return adapter, entry


def parse_size(size: str) -> tuple[int, int]:
    """Parse 'WxH' into (width, height)."""
    try:
        width_s, height_s = size.lower().split("x")
        width, height = int(width_s), int(height_s)
    except (ValueError, AttributeError):
        raise InvalidSizeError(f"Invalid size format: {size!r}")
    if width <= 0 or height <= 0:
        raise InvalidSizeError(f"Invalid size dimensions: {size!r}")
    return width, height