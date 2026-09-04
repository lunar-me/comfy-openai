# ComfyUI OpenAI-compatible API

A thin FastAPI layer that exposes ComfyUI as an OpenAI-compatible image- and
video-generation API.

Applications using the OpenAI Python SDK can generate images and videos through
ComfyUI workflows with no code changes:

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

For quick manual checks against a running server, see the minimal standalone
scripts in `test_scripts/` (one per API mode: list models, generate, edit).

## Endpoints

| Method | Path                    | Description                          |
|--------|-------------------------|--------------------------------------|
| GET    | `/v1/models`            | List available image/video models    |
| POST   | `/v1/images/generations`| Generate an image (OpenAI-compatible)|
| POST   | `/v1/images/edits`      | Edit an image (img2img, OpenAI-compatible)|
| POST   | `/v1/videos/generations`| Generate a video (OpenAI-compatible)|
| GET    | `/images/{file}`        | Serve a saved generated image        |
| GET    | `/videos/{file}`        | Serve a saved generated video        |

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

## Video generation example (text-to-video)

`POST /v1/videos/generations` runs a text-to-video workflow (e.g. the bundled
MiniMax H3 model) and returns each rendered video as a URL and/or base64
payload. It is **synchronous** — the request blocks until the video is ready
(video rendering can take minutes, so the endpoint allows a long render window).

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="local-key")

response = client.videos.generate(
    model="minimax-h3-t2v",
    prompt="A suburban house with a swimming pool at dusk. "
           "A realistic flamingo is floating in the swimming pool.",
    aspect_ratio="16:9 (Widescreen)",
    megapixels=0.4,
    duration=5,          # seconds, 1-15 (also accepts "5s")
    n=1,
)

video_url = response.data[0].url          # http://localhost:8000/videos/<file>
video_data = response.data[0].b64_json   # base64-encoded MP4 bytes
```

Request fields:

| Field          | Type    | Default                | Notes                                   |
|----------------|---------|------------------------|-----------------------------------------|
| `model`        | string  | —                      | Required; a registered video model      |
| `prompt`       | string  | —                      | Required; the text description          |
| `aspect_ratio` | string  | `16:9 (Widescreen)`    | Passed to the workflow's ResolutionSelector |
| `megapixels`   | float   | `0.4`                  | Passed to the workflow's ResolutionSelector |
| `duration`     | float   | `5`                    | Seconds, 1-15; also accepts `"5s"`      |
| `n`            | int     | `1`                    | Number of videos (1-4)                  |
| `response_format` | string | `url`               | `url` or `b64_json`                     |
| `seed`         | int     | `null`                 | Optional; auto-generated when omitted   |

> `aspect_ratio` and `megapixels` are passed straight through to the workflow's
> `ResolutionSelector` node, which only accepts values from fixed lists. The
> server validates them against the model's declared lists and returns a 400
> (`invalid_video_params`) for anything else. The bundled `minimax-h3-t2v`
> model accepts the aspect ratios `16:9 (Widescreen)`, `9:16 (Portrait)`,
> `1:1 (Square)`, `4:3 (Standard)`, `3:4 (Portrait)`, `21:9 (Cinematic)` and
> megapixels `0.4, 0.5, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0`. The workflow itself
> computes the target resolution from these — the API never provides one.

## Video generation example (image-to-video)

`POST /v1/videos/edits` runs an image-to-video workflow (e.g. the bundled
`minimax-h3-i2v` model) from an uploaded image plus a text prompt. It is a
**multipart form** request, mirroring `POST /v1/images/edits`. Image-to-video
takes a target `megapixels` value but **no `aspect_ratio`** — the workflow
derives the resolution from the input image.

```python
import httpx

response = httpx.post(
    "http://localhost:8000/v1/videos/edits",
    headers={"Authorization": "Bearer local-key"},
    data={
        "model": "minimax-h3-i2v",
        "prompt": "The flamingo slowly turns its head toward the camera.",
        "megapixels": "0.6",
        "duration": "5",
        "n": "1",
    },
    files={"image": ("scene.jpg", open("scene.jpg", "rb"), "image/jpeg")},
    timeout=1800.0,
)
response.raise_for_status()
video_url = response.json()["data"][0]["url"]
```

Form fields:

| Field          | Type    | Default | Notes                                   |
|----------------|---------|---------|-----------------------------------------|
| `model`        | string  | —       | Required; a registered video model     |
| `prompt`       | string  | —       | Required; the text description          |
| `image`        | file    | —       | Required; the input image (multipart)   |
| `megapixels`   | float   | `0.4`   | Target megapixels (no aspect_ratio)     |
| `duration`     | float   | `5`     | Seconds, 1-15; also accepts `"5s"`      |
| `n`            | int     | `1`     | Number of videos (1-4)                  |
| `response_format` | string | `url` | `url` or `b64_json`                     |
| `seed`         | int     | `null`  | Optional; auto-generated when omitted   |

> The bundled `minimax-h3-i2v` model accepts megapixels
> `0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0`. Because image-to-video
> has no `aspect_ratio`, that validation is skipped for this endpoint.

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

Three models ship out of the box — `flux` (text-to-image), `flux-edit`
(img2img), and `minimax-h3-t2v` (text-to-video). Each entry carries a `type`
field (`"image"` or `"video"`) that routes it to the correct endpoint. Example:

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
