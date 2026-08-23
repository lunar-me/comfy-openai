import json
from pathlib import Path

from workflows.guess_nodes import guess_nodes

WORKFLOW = json.loads(
    Path("workflows/image_flux2_text_to_image_9b.json").read_text(encoding="utf-8")
)

IMAGE_EDIT_WORKFLOW = json.loads(
    Path("workflows/image_flux2_klein_image_edit_9b_base.json").read_text(
        encoding="utf-8"
    )
)


def test_guess_nodes_matches_known_registry():
    """The guesses for the bundled workflow should match models.json exactly."""
    guesses = guess_nodes(WORKFLOW)
    nodes = {role: entry["node"] for role, entry in guesses.items()}

    expected = {
        "prompt": "75:74",
        "negative_prompt": "75:67",
        "seed": "75:73",
        "width": "75:68",
        "height": "75:69",
        "latent": "75:66",
        "steps": "75:62",
        "cfg": "75:63",
    }
    assert nodes == expected


def test_guess_nodes_detects_input_image():
    """The image-edit workflow's reference image (LoadImage) node is detected."""
    guesses = guess_nodes(IMAGE_EDIT_WORKFLOW)
    nodes = {role: entry["node"] for role, entry in guesses.items()}

    assert nodes["input_image"] == "76"
    assert nodes["prompt"] == "75:74"
    assert nodes["negative_prompt"] == "75:67"
    assert nodes["seed"] == "75:73"
    assert nodes["latent"] == "75:66"
    assert nodes["steps"] == "75:62"
    assert nodes["cfg"] == "75:63"
    # The image-edit workflow has no primitive width/height nodes.
    assert "width" not in nodes
    assert "height" not in nodes


def test_guess_nodes_reports_confidence():
    guesses = guess_nodes(WORKFLOW)
    for role, entry in guesses.items():
        assert "node" in entry
        assert "alternatives" in entry
        assert 0.0 < entry["confidence"] <= 1.0