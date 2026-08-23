# Workflows Configuration

This directory holds everything needed to register a ComfyUI workflow as an
OpenAI-compatible image model — **without changing any Python code**.

## Files

| File            | Purpose                                                        |
|-----------------|----------------------------------------------------------------|
| `models.json`   | The **model registry** — maps a model name to a workflow + node map |
| `*.json`        | ComfyUI **API-format** workflow files (e.g. `image_flux2_text_to_image_9b.json`) |

## How the model registry works

`workflows/models.json` is a JSON object keyed by **model name** (the value you
pass as `model` in an OpenAI request). Each entry describes:

```jsonc
{
  "flux": {
    "workflow": "workflows/image_flux2_text_to_image_9b.json", // path to the API-format workflow JSON
    "nodes": {
      "prompt": "75:74",            // node ID holding the positive prompt
      "negative_prompt": "75:67",   // optional: node ID for negative prompt
      "seed": "75:73",              // node ID holding the noise seed
      "width": "75:68",             // node ID for the width primitive
      "height": "75:69",            // node ID for the height primitive
      "latent": "75:66",            // node ID for the latent (batch_size)
      "steps": "75:62",             // optional: node ID for steps
      "cfg": "75:63"                // optional: node ID for cfg
    },
    "sizes": ["1024x1024", "512x512", "768x768"], // accepted size strings
    "owned_by": "local"                            // shown in /v1/models
  }
}
```

The app loads this file at request time (path configurable via
`WORKFLOW_REGISTRY` in `.env`). Edit it and your models appear immediately —
**no code, no restart required** (the registry is re-read per request).

## Setting up a new workflow — step by step

### 1. Export the workflow in API format

In ComfyUI:

1. Load / build your workflow graph in the editor.
2. Menu → **Workflow** → **Export (API)** (or use the ComfyUI API-format export).
3. Save the resulting `.json` into this `workflows/` folder, e.g. `workflows/my_workflow.json`.

> The **API format** looks like a flat object of node IDs
> (`{"75:74": {"inputs": {...}, "class_type": "..."}, ...}`).
> The **UI format** (the graph editor save) is a nested
> `{"nodes": [...], "links": [...]}` object — that will **not** work.

### 2. Identify the node IDs for the fields you want to override

You need to know which node IDs correspond to:

| Field            | Node class to look for                    | Input key        |
|------------------|-------------------------------------------|------------------|
| `prompt`         | `CLIPTextEncode` (positive)               | `text`           |
| `negative_prompt`| `CLIPTextEncode` (negative)               | `text`           |
| `seed`           | `RandomNoise`                             | `noise_seed`     |
| `width`          | `PrimitiveInt` (width)                    | `value`          |
| `height`         | `PrimitiveInt` (height)                   | `value`          |
| `latent`         | `Empty*LatentImage` / `EmptyFlux2LatentImage` | `batch_size` |
| `steps`          | `*Scheduler` (e.g. `Flux2Scheduler`)      | `steps`          |
| `cfg`            | `CFGGuider`                               | `cfg`            |

Open your exported JSON and find the node IDs, then record them. For example,
the `Flux2Scheduler` node `75:62` has `"inputs": {"steps": 20, ...}`, so
`"steps": "75:62"`.

Only `prompt`, `seed`, `width`, `height`, and `latent` are **required**.
`negative_prompt`, `steps`, and `cfg` are optional — omit them if your workflow
doesn't have those nodes, and the adapter will simply skip them.

### 3. Register the model in `models.json`

Add a new key to `workflows/models.json`:

```json
{
  "flux": { "...": "existing entry..." },
  "my_model": {
    "workflow": "workflows/my_workflow.json",
    "nodes": {
      "prompt": "1:74",
      "seed": "1:73",
      "width": "1:68",
      "height": "1:69",
      "latent": "1:66"
    },
    "sizes": ["1024x1024", "768x768"],
    "owned_by": "local"
  }
}
```

### 4. Use it

The new model is immediately available via the OpenAI-compatible API:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="local-key")
response = client.images.generate(
    model="my_model",
    prompt="A painting of a lighthouse at dusk",
    size="1024x1024",
)
```

It will also show up in `GET /v1/models`.

## Changing the registry location

By default the app reads `workflows/models.json`. To point at a different file,
set `WORKFLOW_REGISTRY` in your `.env`:

```
WORKFLOW_REGISTRY=/absolute/path/to/my-models.json
```
