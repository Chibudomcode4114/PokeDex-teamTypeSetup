"""Raw JSON disk cache for PokeAPI HTTP responses.

Caches external PokeAPI payloads to prevent redundant network requests and enable
offline reproducibility. Corrupted cache files are handled gracefully by ignoring
them and allowing a fresh fetch.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PokeApiCache:
    """Filesystem-based raw JSON response cache for PokeAPI payloads."""

    def __init__(self, cache_dir: Path | str) -> None:
        self.cache_dir = Path(cache_dir)

    def _resolve_path(self, endpoint: str, identifier: str) -> Path:
        """Resolve a deterministic file path for a cached resource."""
        safe_endpoint = endpoint.strip("/").replace("/", "_")
        safe_identifier = identifier.strip("/").replace("/", "_")
        return self.cache_dir / safe_endpoint / f"{safe_identifier}.json"

    def get(self, endpoint: str, identifier: str) -> dict[str, Any] | None:
        """Retrieve a cached raw JSON payload if present and valid.

        Returns None if the cache file does not exist, is empty, or is corrupted.
        """
        path = self._resolve_path(endpoint, identifier)
        if not path.is_file():
            return None

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                logger.warning("Cache entry at %s did not contain a JSON object. Ignoring.", path)
                return None
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            logger.warning("Corrupted cache entry at %s (%s). Treating as cache miss.", path, e)
            return None

    def set(self, endpoint: str, identifier: str, data: dict[str, Any]) -> None:
        """Persist a raw JSON payload to disk."""
        path = self._resolve_path(endpoint, identifier)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            temp_path.replace(path)
        except OSError as e:
            logger.warning("Failed to write PokeAPI cache to %s: %s", path, e)
