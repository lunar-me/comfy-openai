from app.comfy.workflow import WorkflowAdapter, parse_size

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
