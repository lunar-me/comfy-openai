from app.comfy.workflow import (
    InvalidVideoParamsError,
    ModelNotFoundError,
    VideoWorkflowAdapter,
    WorkflowAdapter,
    get_adapter,
    get_video_adapter,
    load_models,
    parse_size,
    validate_video_params,
)

# Node map mirrors workflows/image_flux2_text_to_image_9b.json
NODE_MAP = {
    "prompt": "75:74",
    "negative_prompt": "75:67",
    "seed": "75:73",
    "width": "75:68",
    "height": "75:69",
    "latent": "75:66",
    "steps": "75:62",
    "cfg": "75:63",
}


def test_load_models_returns_registry():
    registry = load_models("workflows/models.json")
    assert "flux" in registry
    assert registry["flux"]["workflow"] == "workflows/image_flux2_text_to_image_9b.json"
    assert registry["flux"]["nodes"]["prompt"] == "75:74"


def test_get_adapter_resolves_model():
    adapter, meta = get_adapter("flux")
    assert isinstance(adapter, WorkflowAdapter)
    assert meta["owned_by"] == "local"


def test_get_adapter_unknown_model_raises():
    try:
        get_adapter("does-not-exist")
    except ModelNotFoundError:
        return
    raise AssertionError("Expected ModelNotFoundError")


def test_build_injects_values():
    adapter = WorkflowAdapter("workflows/image_flux2_text_to_image_9b.json", NODE_MAP)
    workflow = adapter.build(
        prompt="a test prompt",
        width=512,
        height=768,
        seed=42,
        n=2,
    )

    assert workflow["75:74"]["inputs"]["text"] == "a test prompt"
    assert workflow["75:67"]["inputs"]["text"] == ""
    assert workflow["75:73"]["inputs"]["noise_seed"] == 42
    assert workflow["75:68"]["inputs"]["value"] == 512
    assert workflow["75:69"]["inputs"]["value"] == 768
    assert workflow["75:66"]["inputs"]["batch_size"] == 2


def test_seed_auto_generated_when_none():
    adapter = WorkflowAdapter("workflows/image_flux2_text_to_image_9b.json", NODE_MAP)
    workflow = adapter.build(prompt="x", width=1024, height=1024, seed=None)
    assert isinstance(workflow["75:73"]["inputs"]["noise_seed"], int)


def test_parse_size_valid():
    assert parse_size("1024x1024") == (1024, 1024)
    assert parse_size("512X768") == (512, 768)


# --- Video workflow adapter ---------------------------------------------------

VIDEO_NODE_MAP = {
    "prompt": "105:104",
    "resolution_selector": "115",
    "duration": "105:111",
    "seed": "105:15",
}


def test_get_video_adapter_resolves_model():
    adapter, meta = get_video_adapter("minimax-h3-t2v")
    assert isinstance(adapter, VideoWorkflowAdapter)
    assert meta["type"] == "video"


def test_get_video_adapter_rejects_image_model():
    try:
        get_video_adapter("flux")
    except ModelNotFoundError:
        return
    raise AssertionError("Expected ModelNotFoundError for image model on video endpoint")


def test_video_adapter_injects_values():
    adapter = VideoWorkflowAdapter("workflows/MINIMAX H3 T2V.json", VIDEO_NODE_MAP)
    workflow = adapter.build(
        prompt="a test video",
        aspect_ratio="16:9 (Widescreen)",
        megapixels=0.6,
        duration=7,
        seed=42,
    )

    assert workflow["105:104"]["inputs"]["prompt"] == "a test video"
    assert workflow["115"]["inputs"]["aspect_ratio"] == "16:9 (Widescreen)"
    assert workflow["115"]["inputs"]["megapixels"] == 0.6
    assert workflow["105:111"]["inputs"]["value"] == 7
    assert workflow["105:15"]["inputs"]["noise_seed"] == 42


def test_video_adapter_seed_auto_generated_when_none():
    adapter = VideoWorkflowAdapter("workflows/MINIMAX H3 T2V.json", VIDEO_NODE_MAP)
    workflow = adapter.build(
        prompt="x",
        aspect_ratio="16:9 (Widescreen)",
        megapixels=0.4,
        duration=5,
        seed=None,
    )
    assert isinstance(workflow["105:15"]["inputs"]["noise_seed"], int)


# --- Image-to-video (MiniMax H3 I2V) ------------------------------------------

I2V_NODE_MAP = {
    "input_image": "114",
    "prompt": "105:104",
    "megapixels": "119",
    "duration": "105:111",
    "seed": "105:15",
}


def test_get_video_adapter_resolves_i2v_model():
    adapter, meta = get_video_adapter("minimax-h3-i2v")
    assert isinstance(adapter, VideoWorkflowAdapter)
    assert meta["type"] == "video"
    # Image-to-video has no aspect_ratio — only a target megapixels node.
    assert "resolution_selector" not in meta["nodes"]
    assert meta["nodes"]["megapixels"] == "119"


def test_i2v_adapter_injects_image_and_megapixels():
    adapter = VideoWorkflowAdapter("workflows/MINIMAX H3 I2V.json", I2V_NODE_MAP)
    workflow = adapter.build(
        prompt="a test video",
        megapixels=0.6,
        duration=7,
        seed=42,
        input_image="scene 06.jpg",
    )

    assert workflow["105:104"]["inputs"]["prompt"] == "a test video"
    assert workflow["114"]["inputs"]["image"] == "scene 06.jpg"
    assert workflow["119"]["inputs"]["megapixels"] == 0.6
    assert workflow["105:111"]["inputs"]["value"] == 7
    assert workflow["105:15"]["inputs"]["noise_seed"] == 42


def test_i2v_adapter_skips_resolution_selector_when_absent():
    # The I2V workflow has no ResolutionSelector node; build must not touch one.
    adapter = VideoWorkflowAdapter("workflows/MINIMAX H3 I2V.json", I2V_NODE_MAP)
    workflow = adapter.build(
        prompt="x",
        megapixels=0.4,
        duration=5,
        seed=1,
        input_image="scene 06.jpg",
    )
    assert "115" not in workflow


def test_validate_video_params_accepts_valid_values():
    meta = {
        "aspect_ratios": ["16:9 (Widescreen)", "4:3 (Standard)"],
        "megapixels": [0.4, 0.6],
    }
    validate_video_params("16:9 (Widescreen)", 0.6, meta)  # should not raise


def test_validate_video_params_rejects_bad_aspect_ratio():
    meta = {"aspect_ratios": ["16:9 (Widescreen)"], "megapixels": [0.4]}
    try:
        validate_video_params("5:4 (Bogus)", 0.4, meta)
    except InvalidVideoParamsError as exc:
        assert exc.param == "aspect_ratio"
        return
    raise AssertionError("Expected InvalidVideoParamsError")


def test_validate_video_params_rejects_bad_megapixels():
    meta = {"aspect_ratios": ["16:9 (Widescreen)"], "megapixels": [0.4]}
    try:
        validate_video_params("16:9 (Widescreen)", 3.5, meta)
    except InvalidVideoParamsError as exc:
        assert exc.param == "megapixels"
        return
    raise AssertionError("Expected InvalidVideoParamsError")


def test_validate_video_params_skips_when_lists_absent():
    # Models that don't declare fixed lists are left unvalidated (passthrough).
    validate_video_params("anything", 123.0, {})  # should not raise
