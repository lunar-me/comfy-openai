# API Test Scripts

Minimal standalone scripts, one per supported API mode. Each talks to a **running**
API server over HTTP, prints the result, and (for generation/edit) saves the
returned image to the current directory.

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

All scripts load a `.env` file into the environment, then read settings via
`os.environ.get(...)`. The script-local `.env` (i.e. `test_scripts/.env`) is
preferred, with the project-root `.env` as a fallback. Real OS environment
variables always take precedence over `.env` values. If neither is set,
sensible defaults are used.

| Variable       | Default                    | Purpose |
|----------------|----------------------------|---------|
| `BASE_URL`     | `http://localhost:8000/v1` | API base URL (must include `/v1`) |
| `API_KEY`      | `local-key`                | API key (sent as Bearer token) |
| `MODEL`        | `flux` / `flux-edit` / `minimax-h3-t2v` | Model id used by the script |
| `OUTPUT_IMAGE` | `response_image`           | Base filename for saved images (02 and 03). The correct extension (`.png` / `.jpg`) is detected from the image bytes and appended automatically. |
| `OUTPUT_VIDEO` | `response_video`           | Base filename for the saved video (04). Always saved as `.mp4`. |

Copy `.env.example` to `test_scripts/.env` and edit as needed:

```bash
cp ../.env.example test_scripts/.env
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
| `04_generate_video.py`  | Text-to-video generation          | `POST /v1/videos/generations` |

## Usage

```bash
# 1. List models
python test_scripts/01_list_models.py

# 2. Generate an image from a prompt (saves response_image.<png|jpg>)
python test_scripts/02_generate_image.py

# 3. Edit an image (pass a path to an input image; saves response_image.<png|jpg>)
python test_scripts/03_edit_image.py path/to/original.png

# 4. Generate a video from a prompt (saves response_video.mp4)
python test_scripts/04_generate_video.py

# 04 takes the prompt and output name from the command line too:
#   prompt on the CLI
python test_scripts/04_generate_video.py --prompt "A cat surfing at sunset"
#   prompt read from a text file
python test_scripts/04_generate_video.py --prompt-file prompt.txt
#   custom output filename (a missing .mp4 is appended)
python test_scripts/04_generate_video.py --prompt "A cat surfing" -o my_video.mp4
```

Prompt precedence: `--prompt` (CLI) > `--prompt-file` (file contents) > the default
test prompt. Output filename precedence: `-o/--output` > `OUTPUT_VIDEO` env var >
`response_video` (always saved as `.mp4`).

## Output

Scripts 02 and 03 save the generated image to the current directory using the
base name from `OUTPUT_IMAGE` (default `response_image`). The file extension
is detected from the image's magic bytes — `.png` for PNG, `.jpg` for JPEG —
so the saved file is always correct regardless of what the backend returns.