# API Test Scripts

Minimal standalone scripts, one per supported API mode. Each talks to a **running**
API server over HTTP and prints the result.

## Prerequisites

1. Start the API server (with a reachable ComfyUI):
   ```bash
   python main.py
   ```
2. Install dependencies (in `requirements.txt`):
   ```bash
   pip install -r requirements.txt
   ```
   The scripts need `httpx` (HTTP client) and `python-dotenv` (`.env` loading).

## Configuration

All scripts read these settings from environment variables **or** the project-root
`.env` file (see [`.env.example`](../.env.example)). Real OS environment variables
always take precedence over `.env` values. If no `.env` file exists, sensible
defaults are used.

| Variable   | Default                  | Purpose                        |
|------------|--------------------------|--------------------------------|
| `BASE_URL` | `http://localhost:8000`  | API base URL. The scripts append `/v1` automatically if missing. |
| `API_KEY`  | `local-key`              | API key (sent as Bearer token)|
| `MODEL`    | `flux` / `flux-edit`     | Model id used by the script   |

Copy `.env.example` to `.env` and edit as needed:

```bash
cp ../.env.example ../.env
```

Example override (shell env wins over `.env`):

```bash
BASE_URL=http://localhost:8000/v1 MODEL=flux-edit python test_scripts/03_edit_image.py in.png
```

## Scripts

| Script                  | API mode                          | Endpoint                |
|-------------------------|-----------------------------------|-------------------------|
| `01_list_models.py`     | List available models             | `GET /v1/models`        |
| `02_generate_image.py`  | Text-to-image generation          | `POST /v1/images/generations` |
| `03_edit_image.py`      | Image edit (img2img)              | `POST /v1/images/edits` |

## Usage

```bash
# 1. List models
python test_scripts/01_list_models.py

# 2. Generate an image from a prompt
python test_scripts/02_generate_image.py

# 3. Edit an image (pass a path to an input image)
python test_scripts/03_edit_image.py path/to/original.png
```
