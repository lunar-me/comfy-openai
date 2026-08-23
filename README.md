# ComfyUI OpenAI-compatible API

A thin FastAPI layer that exposes ComfyUI as an OpenAI-compatible image-generation API.

Applications using the OpenAI Python SDK can generate images through ComfyUI workflows with no code changes:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="local-key",
)

response = client.images.generate(
    model="flux",
    prompt="A highly detailed photograph of a samurai standing in Tokyo at night",
    size="1024x1024",
)

print(response.data[0].url)
```

## Architecture

```text
OpenAI SDK
    |
    v
FastAPI :8000   -> validate request, resolve model, inject prompt/size/seed
    |
    v
ComfyUI :8188   -> POST /prompt -> wait -> GET /history/{id} -> GET /view
    |
    v
OpenAI-compatible response (url or b64_json)
```

## Requirements

- Python 3.10+
- A running ComfyUI instance (default `http://localhost:8188`, configurable via `.env`)
- The Flux2 API-format workflow at `workflows/image_flux2_text_to_image_9b.json`

## Setup

```bash
pip install -r requirements.txt
```

Create your environment file from the template and adjust as needed:

```bash
cp .env.example .env
```

Key settings in `.env`:

| Variable           | Default                    | Description                                   |
|--------------------|----------------------------|-----------------------------------------------|
| `COMFY_URL`        | `http://localhost:8188`    | ComfyUI server address                        |
| `API_PORT`         | `8000`                     | Port the FastAPI server listens on            |
| `BASE_URL`         | `http://localhost:8000`    | Public base URL used in image URLs            |
| `WORKFLOW_REGISTRY`| `workflows/models.json`    | Path to the model registry config file        |

## Run

```bash
python main.py
```

The API listens on `http://localhost:8000`.

## Tests

```bash
python -m pytest tests/ -v
```

## Endpoints

| Method | Path                    | Description                          |
|--------|-------------------------|--------------------------------------|
| GET    | `/v1/models`            | List available image models          |
| POST   | `/v1/images/generations`| Generate an image (OpenAI-compatible)|
| POST   | `/v1/images/edits`      | Edit an image (img2img, OpenAI-compatible)|
| GET    | `/images/{file}`        | Serve a saved generated image        |

## Request example

```json
{
  "model": "flux",
  "prompt": "A cinematic photograph of a fox in Tokyo",
  "size": "1024x1024",
  "n": 1,
  "response_format": "b64_json",
  "seed": 12345
}
```

Supported options: `model`, `prompt`, `n` (1-4), `size`, `response_format`,
`seed`, and optional `negative_prompt`, `steps`, `cfg`.

Each generated image returns **both** `url` and `b64_json`, so both access
patterns always work regardless of `response_format`:

```python
response = client.images.generate(model="flux", prompt="...", size="1024x1024")

image_url = response.data[0].url          # http://localhost:8000/images/<file>
image_data = response.data[0].b64_json    # base64-encoded PNG bytes
```

## Image edit example (img2img)

`POST /v1/images/edits` accepts an input image (and optional mask) plus a
prompt, uploads the image to ComfyUI, and runs the model's image-to-image
workflow:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="local-key")

response = client.images.edit(
    model="flux-edit",
    image=open("original_image.png", "rb"),
    prompt="Add a realistic flamingo floating in the swimming pool",
    n=1,
)

image_b64 = response.data[0].b64_json
```

The edit uses the `input_image` node of the img2img workflow (detected by
`guess_nodes.py` and registered in `workflows/models.json`). `size` is
optional — when omitted, the workflow derives dimensions from the input image.

## How it works

1. `POST /v1/images/generations` validates the request.
2. The model name is resolved against the registry in `workflows/models.json`.
3. The `WorkflowAdapter` injects the prompt, dimensions, seed, and batch size
   into the ComfyUI API-format workflow (it is the only code that knows node IDs).
4. The workflow is submitted to ComfyUI via `POST /prompt`, and the server
   polls `/history/{id}` until execution completes.
5. The generated image is retrieved via `/view` and returned as base64 or
   saved to `output/` and exposed as a URL.

## Models

The model registry lives in **`workflows/models.json`** — a config file, not code.
It maps model names to their workflow JSON and node map, so you can register any
ComfyUI workflow **without changing Python code**.

Two models ship out of the box — `flux` (text-to-image) and `flux-edit`
(img2img). Example:

```json
{
  "flux": {
    "workflow": "workflows/image_flux2_text_to_image_9b.json",
    "nodes": {
      "prompt": "75:74",
      "negative_prompt": "75:67",
      "seed": "75:73",
      "width": "75:68",
      "height": "75:69",
      "latent": "75:66",
      "steps": "75:62",
      "cfg": "75:63"
    },
    "sizes": ["1024x1024", "512x512", "768x768"],
    "owned_by": "local"
  }
}
```

To add a model: export your workflow from ComfyUI in **API format**, drop the
`.json` into `workflows/`, and add a matching entry to `workflows/models.json`.
The new model is available immediately (the registry is re-read per request).
See **`workflows/README.md`** for the full step-by-step guide.
