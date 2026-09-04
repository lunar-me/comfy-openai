#!/usr/bin/env python3
"""Guess node roles in a ComfyUI API-format workflow.

This helper reads a ComfyUI **API-format** workflow JSON (the flat
``{node_id: {class_type, inputs, _meta}}`` object exported from the ComfyUI
editor via *Workflow > Export (API)*) and tries to identify which nodes play
each role used by the model registry:

    prompt, negative_prompt, input_image, seed, width, height, latent,
    steps, cfg          (image workflows)
    prompt, resolution_selector, duration, seed   (video workflows)

It writes its best guesses to ``models_guess.json`` in this directory. That
file is **not** read by the application — it is only a starting point. Review
the guesses, fix any that are wrong, and copy them into ``models.json``.

Usage::

    python workflows/guess_nodes.py [workflow.json] [--out OUT]

Examples::

    python workflows/guess_nodes.py workflows/image_flux2_text_to_image_9b.json
    python workflows/guess_nodes.py my_workflow.json --out workflows/models_guess.json

Exit code is 0 on success, 1 on error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DEFAULT_WORKFLOW = Path(__file__).parent / "image_flux2_text_to_image_9b.json"
DEFAULT_OUT = Path(__file__).parent / "models_guess.json"

# Roles we try to guess, in the order they appear in models.json.
ROLES = [
    "prompt",
    "negative_prompt",
    "input_image",
    "seed",
    "width",
    "height",
    "latent",
    "steps",
    "cfg",
    # Video-only roles (MiniMax H3 text-to-video and similar workflows).
    "resolution_selector",
    "duration",
]


def _node_title(node: dict) -> str:
    """Return the human-readable title of a node, lowercased."""
    meta = node.get("_meta") or {}
    return str(meta.get("title", "")).lower()


def _node_class(node: dict) -> str:
    """Return the node's class_type, lowercased."""
    return str(node.get("class_type", "")).lower()


def _is_clip_text_encode(node: dict) -> bool:
    return _node_class(node) == "cliptextencode"


def guess_nodes(workflow: dict) -> dict:
    """Return {role: node_id} guesses for a parsed API-format workflow."""
    nodes = workflow

    candidates: dict[str, list[str]] = {role: [] for role in ROLES}

    for node_id, node in nodes.items():
        cls = _node_class(node)
        title = _node_title(node)
        inputs = node.get("inputs") or {}

        # prompt / negative_prompt: CLIPTextEncode
        if _is_clip_text_encode(node):
            if "negative" in title:
                candidates["negative_prompt"].append(node_id)
            elif "positive" in title or "prompt" in title:
                candidates["prompt"].append(node_id)
            else:
                candidates["prompt"].append(node_id)

        # prompt (video): nodes that take a raw `prompt` input, e.g.
        # MiniMaxH3ImageToVideo. (CLIPTextEncode uses `text`, handled above.)
        if "prompt" in inputs and not _is_clip_text_encode(node):
            candidates["prompt"].append(node_id)

        # input_image: LoadImage (reference image for img2img workflows)
        if "loadimage" in cls:
            candidates["input_image"].append(node_id)

        # seed: RandomNoise or a node with noise_seed
        if "randomnoise" in cls or "noise_seed" in inputs or "seed" in inputs:
            candidates["seed"].append(node_id)

        # width / height: PrimitiveInt with matching title
        if cls in ("primitiveint", "primitive"):
            if "width" in title:
                candidates["width"].append(node_id)
            elif "height" in title:
                candidates["height"].append(node_id)
            else:
                candidates["width"].append(node_id)
                candidates["height"].append(node_id)

        # latent: Empty*LatentImage
        if "empty" in cls and "latent" in cls:
            candidates["latent"].append(node_id)

        # steps: any *Scheduler or node with a steps input
        if "scheduler" in cls or "steps" in inputs:
            candidates["steps"].append(node_id)

        # cfg: CFGGuider or node with a cfg input
        if "cfg" in cls or "cfg" in inputs:
            candidates["cfg"].append(node_id)

        # resolution_selector (video): ResolutionSelector node — takes
        # aspect_ratio + megapixels and computes the target resolution.
        if "resolutionselector" in cls:
            candidates["resolution_selector"].append(node_id)

        # duration (video): PrimitiveFloat titled with duration/seconds.
        if "primitivefloat" in cls and (
            "duration" in title or "seconds" in title
        ):
            candidates["duration"].append(node_id)

    # Disambiguation: prefer titled width/height primitives.
    width_guesses = candidates["width"]
    height_guesses = candidates["height"]

    if len(width_guesses) > 1:
        titled = [n for n in width_guesses if "width" in _node_title(nodes[n])]
        candidates["width"] = titled or width_guesses[:1]
    if len(height_guesses) > 1:
        titled = [n for n in height_guesses if "height" in _node_title(nodes[n])]
        candidates["height"] = titled or height_guesses[:1]

    # If width and height resolved to the same ambiguous node, split them.
    if (
        candidates["width"]
        and candidates["height"]
        and candidates["width"][0] == candidates["height"][0]
    ):
        shared = candidates["width"][0]
        other_width = [n for n in width_guesses if n != shared]
        other_height = [n for n in height_guesses if n != shared]
        candidates["width"] = [shared] + other_width
        candidates["height"] = [shared] + other_height

    # Build result with confidence.
    result: dict[str, dict] = {}
    for role in ROLES:
        picks = candidates[role]
        if picks:
            confidence = 1.0 if len(picks) == 1 else 0.5
            result[role] = {
                "node": picks[0],
                "alternatives": picks[1:],
                "confidence": confidence,
            }
    return result


def guess_type(guesses: dict) -> str:
    """Return ``"video"`` if the guesses include video-only roles, else ``"image"``."""
#    if guesses.get("resolution_selector") or guesses.get("duration"):
#        return "video"
    if guesses.get("duration"):
        return "video"
    return "image"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Guess node roles in a ComfyUI API-format workflow and write "
            "models_guess.json."
        )
    )
    parser.add_argument(
        "workflow",
        nargs="?",
        type=Path,
        default=DEFAULT_WORKFLOW,
        help=f"Path to the API-format workflow JSON (default: {DEFAULT_WORKFLOW})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output path for the guesses (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args(argv)

    if not args.workflow.exists():
        print(f"Error: workflow file not found: {args.workflow}", file=sys.stderr)
        return 1

    try:
        data = json.loads(args.workflow.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {args.workflow}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        print(
            f"Error: {args.workflow} is not an API-format workflow "
            "(expected a flat object of node IDs).",
            file=sys.stderr,
        )
        return 1

    guesses = guess_nodes(data)

    # Detect whether this is a video workflow (has video-only roles).
    model_type = guess_type(guesses)

    # Always report the workflow path relative to the current working
    # directory with forward slashes, matching how it appears in models.json.
    try:
        rel_workflow = str(Path(os.path.relpath(args.workflow))).replace(os.sep, "/")
    except ValueError:
        rel_workflow = str(args.workflow)

    output = {
        "workflow": rel_workflow,
        "type": model_type,
        "note": (
            "Auto-generated guesses. models_guess.json is NOT read by the app. "
            "Review these, fix anything wrong, and copy the 'nodes' into "
            "models.json."
        ),
        "nodes": {role: entry["node"] for role, entry in guesses.items()},
        "guesses": guesses,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote guesses to {args.out}")
    print(f"Workflow: {rel_workflow}")
    print(f"Type: {model_type}")
    print("Guessed nodes:")
    for role, entry in guesses.items():
        flag = "?" if entry["confidence"] < 1.0 else " "
        print(f"  {flag} {role:<15} -> {entry['node']}")
        for alt in entry["alternatives"]:
            print(f"      alternative: {alt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
