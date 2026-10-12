"""smart-able export: SMART-exact data model XML and the migration bundle.

Run as `uv run python -m export --work DIR [ca_id ...]` (see __main__.py);
the ./smart-able launcher does that for `./smart-able export`.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def version() -> str:
    """`git describe` of the checkout, or 'unknown' outside git."""
    try:
        return subprocess.run(["git", "-C", str(ROOT), "describe", "--tags", "--always", "--dirty"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
