#!/usr/bin/env python3
"""Shared helper for the API test scripts.

Loads a ``.env`` file into ``os.environ`` so every test script can be
configured from a single file instead of relying only on shell environment
variables. The script-local ``.env`` (``test_scripts/.env``) is preferred,
with the project-root ``.env`` as a fallback. Real OS environment variables
always take precedence over values read from ``.env``.

Usage::

    from _env import load_env

    load_env()
    base_url = os.environ.get("BASE_URL", "http://localhost:8000/v1")
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback parser is used
    load_dotenv = None

_loaded = False


def load_env() -> None:
    """Load ``.env`` into ``os.environ`` (once).

    The script-local ``.env`` (``test_scripts/.env``) is preferred; the
    project-root ``.env`` is used as a fallback. Real OS environment variables
    always take precedence over values read from ``.env``.
    """
    global _loaded
    if _loaded:
        return
    _loaded = True

    script_dir = Path(__file__).resolve().parent
    root = script_dir.parent

    # Prefer the script's own directory, fall back to the project root.
    env_path = script_dir / ".env"
    if not env_path.exists():
        env_path = root / ".env"

    if load_dotenv is not None:
        # override=False: existing OS vars win over .env values.
        load_dotenv(env_path, override=False)
    elif env_path.exists():
        _parse_simple(env_path)


def _parse_simple(env_path: Path) -> None:
    """Minimal ``.env`` parser, used only when python-dotenv is missing."""
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def api_base_url(default: str = "http://localhost:8000/v1") -> str:
    """Return the API base URL from ``BASE_URL``, normalized to include ``/v1``.

    Users often set ``BASE_URL`` to the app's origin (``http://localhost:8000``)
    instead of the API endpoint (``http://localhost:8000/v1``). Normalizing here
    means either form works, so a missing ``/v1`` can never direct a request at
    the wrong path — e.g. a POST to the static ``/videos`` mount, which only
    serves GET and would otherwise return ``405 Method Not Allowed``.
    """
    base = os.environ.get("BASE_URL", default).rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    return base