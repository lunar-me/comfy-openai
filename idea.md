For the MVP, I would keep it deliberately small: **FastAPI is the compatibility layer; ComfyUI remains the inference engine.**

ComfyUI already gives us the key primitives we need: submit an API-format workflow to `/prompt`, receive a `prompt_id`, monitor execution over `/ws`, and retrieve output files through `/history`/`/view`. ([ComfyUI][1])

## 1. MVP architecture

```text
                         ┌──────────────────────┐
                         │ Existing application  │
                         │                      │
                         │ OpenAI Python SDK    │
                         └──────────┬───────────┘
                                    │
                                    │ POST /v1/images/generations
                                    ▼
                    ┌─────────────────────────────┐
                    │       FastAPI server        │
                    │                             │
                    │  OpenAI-compatible API      │
                    │                             │
                    │  /v1/models                 │
                    │  /v1/images/generations     │
                    │                             │
                    │  ┌───────────────────────┐  │
                    │  │ Request validation     │  │
                    │  │ Model → workflow      │  │
                    │  │ Prompt injection      │  │
                    │  │ Size/seed injection   │  │
                    │  └──────────┬────────────┘  │
                    └─────────────┼───────────────┘
                                  │
                                  │ HTTP / WebSocket
                                  ▼
                    ┌─────────────────────────────┐
                    │          ComfyUI            │
                    │        localhost:8188       │
                    │                             │
                    │  workflow → sampler → VAE  │
                    │                 ↓           │
                    │              image          │
                    └─────────────┬───────────────┘
                                  │
                                  ▼
                              PNG / JPEG
```

The first version only needs **one ComfyUI instance and one GPU**.

Don't introduce Redis, Celery, PostgreSQL, S3, Kubernetes, etc. yet.

---

# 2. Project structure

I'd start with this:

```text
comfy-openai/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── api/
│   │   └── images.py
│   │
│   ├── models/
│   │   └── openai.py
│   │
│   ├── comfy/
│   │   ├── client.py
│   │   ├── workflow.py
│   │   └── executor.py
│   │
│   ├── storage/
│   │   └── images.py
│   │
│   └── config.py
│
├── workflows/
│   └── flux.json
│
├── output/
│
├── tests/
│   ├── test_images.py
│   └── test_workflow.py
│
├── .env
├── requirements.txt
└── README.md
```

The important separation is:

```text
OpenAI API
    ↓
ComfyUI client
    ↓
Workflow manipulation
    ↓
ComfyUI
```

Don't mix those concerns together.

---

# 3. The API we expose

For the first release, I'd implement only:

```text
GET  /v1/models
POST /v1/images/generations
```

Potentially later:

```text
POST /v1/images/edits
```

The generation request could accept:

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

The OpenAI-compatible part is important, but **don't obsess over reproducing every obscure parameter** initially.

For example:

* `model` → workflow
* `prompt` → CLIP/text encoder node
* `size` → width/height nodes
* `n` → repeat workflow
* `response_format` → URL/base64
* `seed` → sampler

That's enough to make the SDK integration useful.

---

# 4. Pydantic models

Something along these lines:

```python
from typing import Literal
from pydantic import BaseModel, Field


class ImageGenerationRequest(BaseModel):
    model: str
    prompt: str
    n: int = Field(default=1, ge=1, le=4)
    size: str = "1024x1024"
    response_format: Literal["url", "b64_json"] = "url"
    seed: int | None = None


class ImageData(BaseModel):
    url: str | None = None
    b64_json: str | None = None


class ImageGenerationResponse(BaseModel):
    created: int
    data: list[ImageData]
```

I would **not** copy OpenAI's entire schema at this stage.

Implement what your ComfyUI workflows can actually support.

---

# 5. Model → workflow registry

This is the part I'd make particularly clean.

```python
WORKFLOWS = {
    "flux": "workflows/flux.json",
    "sdxl": "workflows/sdxl.json",
}
```

Then:

```python
workflow = load_workflow(WORKFLOWS[request.model])
```

Eventually you can move this into YAML:

```yaml
models:
  flux:
    workflow: workflows/flux.json
    prompt_node: "6"
    sampler_node: "12"
    width_node: "10"
    height_node: "11"

  sdxl:
    workflow: workflows/sdxl.json
    prompt_node: "4"
    sampler_node: "9"
    width_node: "7"
    height_node: "8"
```

This is much better than hard-coding:

```python
workflow["6"]["inputs"]["text"] = prompt
```

throughout your application.

---

# 6. Export the ComfyUI workflow correctly

This is important.

In ComfyUI, build your workflow normally, then use **Save (API Format)**.

The API workflow is a graph whose keys are node IDs and whose values contain `class_type` and `inputs`. That's the format ComfyUI expects when you submit it to `/prompt`. ([ComfyUI][1])

For example, conceptually:

```json
{
  "6": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "PLACEHOLDER_PROMPT",
      "clip": ["4", 0]
    }
  },
  "10": {
    "class_type": "EmptyLatentImage",
    "inputs": {
      "width": 1024,
      "height": 1024,
      "batch_size": 1
    }
  },
  "12": {
    "class_type": "KSampler",
    "inputs": {
      "seed": 12345,
      "steps": 28
    }
  }
}
```

Your server modifies those values before sending the graph to ComfyUI.

---

# 7. Workflow adapter

I'd create a small abstraction:

```python
class WorkflowAdapter:

    def build(
        self,
        prompt: str,
        width: int,
        height: int,
        seed: int | None,
        n: int,
    ) -> dict:
        workflow = load_json(self.workflow_path)

        workflow["6"]["inputs"]["text"] = prompt

        workflow["10"]["inputs"]["width"] = width
        workflow["10"]["inputs"]["height"] = height
        workflow["10"]["inputs"]["batch_size"] = n

        if seed is not None:
            workflow["12"]["inputs"]["seed"] = seed

        return workflow
```

The important idea is that **the rest of the application shouldn't know anything about node IDs**.

Only the workflow adapter should.

---

# 8. ComfyUI client

Then create a very thin client.

```python
import httpx


class ComfyClient:

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def queue_prompt(self, workflow: dict, client_id: str):
        payload = {
            "prompt": workflow,
            "client_id": client_id,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/prompt",
                json=payload,
            )

        response.raise_for_status()
        return response.json()
```

ComfyUI's `/prompt` endpoint validates the workflow and puts it into its execution queue, returning a `prompt_id`. ([ComfyUI][1])

---

# 9. Waiting for the image

There are two sensible ways.

### Option A — WebSocket

This is what I'd use.

```text
POST /prompt
      ↓
prompt_id
      ↓
connect /ws
      ↓
executing events
      ↓
execution complete
      ↓
GET /history/{prompt_id}
      ↓
output filename
      ↓
GET /view?filename=...
```

ComfyUI's own example follows essentially this pattern: queue the prompt, listen to `/ws`, detect completion, then retrieve the generated image. ([GitHub][2])

### Option B — poll history

Simpler:

```text
POST /prompt
      ↓
prompt_id
      ↓
GET /history/{prompt_id}
      ↓
sleep
      ↓
GET /history/{prompt_id}
      ↓
...
```

I'd actually implement **polling first** because it's easier to debug.

Then switch to WebSockets once everything works.

---

# 10. Output handling

Once ComfyUI completes:

```json
{
  "outputs": {
    "9": {
      "images": [
        {
          "filename": "ComfyUI_00001_.png",
          "subfolder": "",
          "type": "output"
        }
      ]
    }
  }
}
```

You can retrieve that image from ComfyUI using `/view`. ComfyUI's documented API includes both `/history` and `/view` for this workflow. ([ComfyUI][1])

Your server then has two choices.

### `response_format="b64_json"`

Read the image:

```python
image_bytes = await ...
encoded = base64.b64encode(image_bytes).decode()
```

Return:

```json
{
  "created": 1787472000,
  "data": [
    {
      "b64_json": "iVBORw0KGgoAAA..."
    }
  ]
}
```

### `response_format="url"`

Save it:

```text
output/
    8c4b0d3e.png
```

and expose:

```text
GET /images/8c4b0d3e.png
```

Then:

```json
{
  "created": 1787472000,
  "data": [
    {
      "url": "http://localhost:8000/images/8c4b0d3e.png"
    }
  ]
}
```

For an MVP, this is perfectly adequate.

---

# 11. FastAPI endpoint

The endpoint becomes surprisingly small:

```python
@router.post("/images/generations")
async def generate_images(
    request: ImageGenerationRequest,
):

    workflow = workflow_registry.build(
        model=request.model,
        prompt=request.prompt,
        size=request.size,
        seed=request.seed,
        n=request.n,
    )

    result = await comfy.execute(workflow)

    images = []

    for image in result.images:

        if request.response_format == "b64_json":
            images.append({
                "b64_json": encode_base64(image),
            })

        else:
            url = storage.save(image)

            images.append({
                "url": url,
            })

    return {
        "created": int(time.time()),
        "data": images,
    }
```

That's basically the whole conceptual API.

---

# 12. OpenAI SDK compatibility

Then this should work:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="local-key",
)

result = client.images.generate(
    model="flux",
    prompt="A photorealistic red panda drinking coffee",
    size="1024x1024",
)

print(result.data[0].url)
```

The application's perspective is:

```text
OpenAI SDK
    ↓
OpenAI-compatible HTTP
```

Your server's perspective is:

```text
HTTP request
    ↓
FastAPI
    ↓
workflow
    ↓
ComfyUI
```

That separation is exactly what we want.

---

# 13. `/v1/models`

I'd implement this too, even though it's trivial.

```http
GET /v1/models
```

returns something like:

```json
{
  "object": "list",
  "data": [
    {
      "id": "flux",
      "object": "model",
      "owned_by": "local"
    },
    {
      "id": "sdxl",
      "object": "model",
      "owned_by": "local"
    }
  ]
}
```

Then an application can discover your available image models.

---

# 14. Error handling

This is one place where I'd spend a little effort.

Suppose ComfyUI rejects the workflow.

Don't return:

```text
500 Internal Server Error
```

with some giant Python traceback.

Instead translate it into an API error:

```json
{
  "error": {
    "message": "ComfyUI workflow validation failed",
    "type": "invalid_request_error",
    "param": "model",
    "code": "workflow_validation_error"
  }
}
```

Similarly:

```text
unknown model
invalid size
invalid n
ComfyUI timeout
ComfyUI execution error
GPU out of memory
```

should become predictable API errors.

This is what makes the wrapper feel like an actual API rather than "FastAPI sitting in front of ComfyUI."

---

# 15. I'd keep the first version synchronous

This is an important choice.

Don't start with:

```text
POST
 ↓
job database
 ↓
Redis
 ↓
worker
 ↓
ComfyUI
 ↓
webhook
```

Instead:

```text
POST /images/generations
        ↓
queue ComfyUI job
        ↓
wait
        ↓
return image
```

For a single GPU, ComfyUI already has its own execution queue. ([ComfyUI][1])

So let ComfyUI do that job.

Later:

```text
POST /images/generations
        ↓
202 + job_id
        ↓
background worker
        ↓
ComfyUI
        ↓
GET /jobs/{id}
```

can be added without changing the workflow abstraction.

---

# 16. `n` deserves a little thought

OpenAI-style APIs allow multiple images.

There are two ways to implement it.

### Approach A — batch

Set:

```python
batch_size = n
```

inside the ComfyUI latent node.

That's the easiest.

### Approach B — separate generations

Submit the workflow `n` times with different seeds.

This is slower but gives you independent generation jobs.

For MVP I'd use **batch size** where the workflow supports it.

---

# 17. The MVP's actual runtime

I'd run:

```text
Terminal 1:

python main.py
```

ComfyUI:

```text
127.0.0.1:8188
```

FastAPI:

```text
127.0.0.1:8000
```

Then:

```text
OpenAI application
       │
       ▼
localhost:8000/v1
       │
       ▼
localhost:8188
       │
       ▼
     GPU
```

Once that's working, put Nginx/Caddy in front if you need remote access.

---

# 18. Dependencies

The initial `requirements.txt` can be tiny:

```text
fastapi
uvicorn[standard]
httpx
pydantic
websockets
python-multipart
```

You don't need a database.

You don't need Redis.

You don't need Celery.

You don't need Docker for the first iteration either.

---

# 19. What I'd implement in order

I'd build it in exactly this sequence:

### Phase 1

```text
✓ FastAPI
✓ POST /v1/images/generations
✓ hardcoded Flux workflow
✓ prompt injection
✓ size injection
✓ seed injection
✓ ComfyUI /prompt
✓ wait for completion
✓ return base64
```

At that point:

```python
client.images.generate(...)
```

works.

### Phase 2

```text
✓ /v1/models
✓ model → workflow registry
✓ URL responses
✓ persistent output directory
✓ proper OpenAI error format
✓ request validation
```

Now it's a genuinely useful local service.

### Phase 3

```text
✓ /images/edits
✓ input image upload
✓ LoRA selection
✓ negative prompts
✓ steps
✓ CFG/guidance
✓ sampler configuration
✓ WebSocket progress
```

### Phase 4

Only if you actually need it:

```text
✓ async jobs
✓ Redis
✓ multiple GPUs
✓ worker processes
✓ persistent database
✓ object storage
✓ authentication
✓ rate limiting
```

---

# 20. One architectural detail I'd strongly recommend

Make **workflow adapters** the boundary between OpenAI semantics and ComfyUI.

Don't do this:

```text
OpenAI request
    ↓
randomly manipulate JSON
    ↓
ComfyUI
```

Do this:

```text
OpenAI request
      ↓
ImageRequest
      ↓
WorkflowAdapter
      ↓
ComfyUI API workflow
      ↓
ComfyUI
```

Then later you can have:

```text
FluxAdapter
SDXLAdapter
QwenImageAdapter
CustomWorkflowAdapter
```

without changing your API.

That is what will make this project scale nicely.

---

## The MVP I would actually target

I'd aim for this exact experience:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="anything",
)

response = client.images.generate(
    model="flux",
    prompt="A highly detailed photograph of a samurai standing in Tokyo at night",
    size="1024x1024",
)

print(response.data[0].url)
```

And underneath:

```text
OpenAI SDK
    │
    ▼
FastAPI :8000
    │
    ├── validate request
    ├── resolve "flux"
    ├── load flux.json
    ├── inject prompt
    ├── inject dimensions
    ├── inject seed
    │
    ▼
ComfyUI :8188
    │
    ├── POST /prompt
    ├── wait for prompt_id
    ├── monitor execution
    ├── GET /history/{prompt_id}
    └── GET /view
    │
    ▼
FastAPI
    │
    └── OpenAI-compatible response
```

**That's the version I'd build first.** It's small enough to understand completely, but the abstractions are already in the right places for turning it into a multi-model/multi-GPU service later.

One caveat: the exact OpenAI image response/request surface changes over time, so I'd treat **"OpenAI-compatible" as compatibility with the subset your clients actually use**, rather than promising byte-for-byte compatibility with every current OpenAI image feature. OpenAI's current API surface also includes newer image-generation behavior beyond the simple `images.generate` flow. ([developers.openai.com][3])

If you want to proceed, the natural next step is to build **the actual runnable MVP**: `main.py`, `images.py`, `comfy/client.py`, `workflow.py`, Pydantic models, a sample Flux API-format workflow, and a `docker-compose.yml` for the API layer.

[1]: https://docs.comfy.org/development/comfyui-server/comms_routes "Routes - ComfyUI"
[2]: https://github.com/Comfy-Org/ComfyUI/blob/master/script_examples/websockets_api_example_ws_images.py "ComfyUI/script_examples/websockets_api_example_ws_images.py at master · Comfy-Org/ComfyUI · GitHub"
[3]: https://developers.openai.com/api/reference/cli/resources/responses/methods/create "Create a model response | OpenAI API Reference"
