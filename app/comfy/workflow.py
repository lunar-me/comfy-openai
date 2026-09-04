import json
import random
from pathlib import Path

from app.config import settings


class ModelNotFoundError(Exception):
    """Raised when a requested model is not registered."""


class InvalidSizeError(Exception):
    """Raised when the requested size is not supported by a model."""


class InvalidVideoParamsError(Exception):
    """Raised when a video request uses an aspect_ratio or megapixels value
    that is not in the model's fixed ResolutionSelector lists."""

    def __init__(self, param: str, message: str):
        super().__init__(message)
        self.param = param


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


class VideoWorkflowAdapter:
    """Boundary between OpenAI video request semantics and ComfyUI API workflow JSON.

    Handles the MiniMax H3 video workflows. Text-to-video exposes a text prompt,
    an aspect_ratio + megapixels pair (the ResolutionSelector node), and a
    duration in seconds (a PrimitiveFloat that the workflow's MathExpression
    node turns into a frame length). Image-to-video additionally takes an input
    image (a LoadImage node) and a target megapixels value (an
    ImageScaleToTotalPixels node) — it has no aspect_ratio.
    """

    def __init__(self, workflow_path: str, node_map: dict):
        self.workflow_path = Path(workflow_path)
        self.node_map = node_map

    def build(
        self,
        prompt: str,
        aspect_ratio: str | None = None,
        megapixels: float | None = None,
        duration: float | None = None,
        seed: int | None = None,
        input_image: str | None = None,
    ) -> dict:
        workflow = self._load()

        # Prompt -> MiniMaxH3ImageToVideo node
        workflow[self.node_map["prompt"]]["inputs"]["prompt"] = prompt

        # Input / reference image (image-to-video): LoadImage node expects its
        # "image" input to be the filename of an image already in ComfyUI.
        if input_image is not None and (img_node := self.node_map.get("input_image")):
            workflow[img_node]["inputs"]["image"] = input_image

        # Resolution: text-to-video uses a ResolutionSelector node that takes an
        # aspect_ratio + megapixels pair. Image-to-video has no aspect_ratio —
        # it only takes a target megapixels value on an ImageScaleToTotalPixels
        # node. Apply whichever node(s) the workflow declares.
        if res_node := self.node_map.get("resolution_selector"):
            if aspect_ratio is not None:
                workflow[res_node]["inputs"]["aspect_ratio"] = aspect_ratio
            if megapixels is not None:
                workflow[res_node]["inputs"]["megapixels"] = megapixels
        if megapixels is not None and (mp_node := self.node_map.get("megapixels")):
            workflow[mp_node]["inputs"]["megapixels"] = megapixels

        # Duration (seconds) -> PrimitiveFloat; the workflow's MathExpression
        # node derives the frame length from this value.
        if duration is not None and (dur_node := self.node_map.get("duration")):
            workflow[dur_node]["inputs"]["value"] = duration

        # Seed
        if seed is None:
            seed = random.randint(0, 2**53 - 1)
        workflow[self.node_map["seed"]]["inputs"]["noise_seed"] = seed

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
    if entry.get("type", "image") != "image":
        raise ModelNotFoundError(f"Model is not an image model: {model}")
    adapter = WorkflowAdapter(entry["workflow"], entry["nodes"])
    return adapter, entry


def get_video_adapter(model: str) -> tuple[VideoWorkflowAdapter, dict]:
    """Return the VideoWorkflowAdapter and its model metadata for a model name."""
    entry = load_models().get(model)
    if entry is None:
        raise ModelNotFoundError(f"Unknown model: {model}")
    if entry.get("type") != "video":
        raise ModelNotFoundError(f"Model is not a video model: {model}")
    adapter = VideoWorkflowAdapter(entry["workflow"], entry["nodes"])
    return adapter, entry


def validate_video_params(
    aspect_ratio: str | None, megapixels: float | None, meta: dict
) -> None:
    """Validate aspect_ratio / megapixels against the model's fixed lists.

    The ResolutionSelector node only accepts values from fixed lists. When a
    model entry declares ``aspect_ratios`` and/or ``megapixels``, reject any
    request value outside those lists with a clear error. Models that don't
    declare the lists are left unvalidated (passthrough). Image-to-video models
    have no aspect_ratio, so that check is skipped when aspect_ratio is None.
    """
    allowed_ratios = meta.get("aspect_ratios")
    if aspect_ratio is not None and allowed_ratios and aspect_ratio not in allowed_ratios:
        raise InvalidVideoParamsError(
            "aspect_ratio",
            f"Invalid aspect_ratio {aspect_ratio!r}. Must be one of: "
            + ", ".join(allowed_ratios),
        )

    allowed_megapixels = meta.get("megapixels")
    if megapixels is not None and allowed_megapixels and megapixels not in allowed_megapixels:
        raise InvalidVideoParamsError(
            "megapixels",
            f"Invalid megapixels {megapixels}. Must be one of: "
            + ", ".join(str(v) for v in allowed_megapixels),
        )


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