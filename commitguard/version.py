"""Version checking utilities."""

from __future__ import annotations

import json
import urllib.request
from urllib.error import URLError
from packaging import version

from . import __version__


def get_latest_version() -> str | None:
    """Fetch latest version from PyPI."""
    try:
        with urllib.request.urlopen(
            "https://pypi.org/pypi/commitguard-cli/json", timeout=2
        ) as response:
            data = json.loads(response.read())
            return data["info"]["version"]
    except (URLError, json.JSONDecodeError, KeyError):
        return None


def check_for_update() -> str | None:
    """Check if a newer version is available."""
    latest = get_latest_version()
    if latest and version.parse(latest) > version.parse(__version__):
        return latest
    return None
