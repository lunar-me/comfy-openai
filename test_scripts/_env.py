#!/usr/bin/env python3
"""Shared helper for the API test scripts.

Loads the project-root ``.env`` file (if present) into ``os.environ`` so every
test script can be configured from a single file instead of relying only on
shell environment variables. Real OS environment variables always take
precedence over values read from ``.env``.

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
    """Load ``.env`` from the project root into ``os.environ`` (once)."""
    global _loaded
    if _loaded:
        return
    _loaded = True

    root = Path(__file__).resolve().parent.parent
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