from __future__ import annotations

import json

from functools import lru_cache
from pathlib import Path
from typing import Any

from django import template
from django.conf import settings

register = template.Library()


def _get_manifest_path() -> Path:
    """Return the React asset manifest path."""
    return Path(str(settings.FRONTEND_ASSET_MANIFEST_PATH))


@lru_cache(maxsize=8)
def _load_manifest(path_str: str, mtime: float | None) -> dict[str, Any]:
    """Load and cache the frontend asset manifest."""
    del mtime
    path = Path(path_str)
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def get_frontend_manifest() -> dict[str, Any]:
    """Return the parsed frontend asset manifest."""
    manifest_path = _get_manifest_path()
    manifest_mtime = (
        manifest_path.stat().st_mtime if manifest_path.exists() else None
    )
    return _load_manifest(str(manifest_path), manifest_mtime)


def frontend_bundle_available() -> bool:
    """Return whether the frontend bundle manifest is available."""
    manifest = get_frontend_manifest()
    files = manifest.get("files", {})
    if isinstance(files, dict) and files:
        return True

    entrypoints = manifest.get("entrypoints", [])
    return isinstance(entrypoints, list) and bool(entrypoints)


def _to_public_asset_path(asset_path: str) -> str:
    if asset_path.startswith(("/", "http://", "https://")):
        return asset_path

    static_url = str(getattr(settings, "STATIC_URL", "/static/")).rstrip("/")
    normalized_path = asset_path.lstrip("/")
    if normalized_path.startswith("static/"):
        normalized_path = normalized_path.removeprefix("static/")

    return f"{static_url}/{normalized_path}"


@register.simple_tag
def frontend_static(asset: str) -> str:
    """Resolve a built frontend asset path from ``asset-manifest.json``."""
    manifest = get_frontend_manifest()

    files = manifest.get("files", {})
    if isinstance(files, dict):
        asset_path = files.get(asset)
        if isinstance(asset_path, str):
            return _to_public_asset_path(asset_path)

    entrypoints = manifest.get("entrypoints", [])
    if isinstance(entrypoints, list):
        if asset.endswith(".css"):
            for entrypoint in entrypoints:
                if isinstance(entrypoint, str) and entrypoint.endswith(".css"):
                    return _to_public_asset_path(entrypoint)
        if asset.endswith(".js"):
            for entrypoint in entrypoints:
                if isinstance(entrypoint, str) and entrypoint.endswith(".js"):
                    return _to_public_asset_path(entrypoint)

    return asset
