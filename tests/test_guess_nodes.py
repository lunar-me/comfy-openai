import json
from pathlib import Path

from workflows.guess_nodes import guess_nodes

WORKFLOW = json.loads(
    Path("workflows/image_flux2_text_to_image_9b.json").read_text(encoding="utf-8")
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


def test_guess_nodes_reports_confidence():
    guesses = guess_nodes(WORKFLOW)
    for role, entry in guesses.items():
        assert "node" in entry
        assert "alternatives" in entry
        assert 0.0 < entry["confidence"] <= 1.0