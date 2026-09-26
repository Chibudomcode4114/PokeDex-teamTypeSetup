"""Asynchronous HTTP client for PokeAPI with bounded retries and raw disk caching."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import httpx

from app.adapters.pokeapi.cache import PokeApiCache
from app.adapters.pokeapi.exceptions import (
    PokeApiError,
    PokeApiNotFoundError,
    PokeApiRateLimitError,
    PokeApiServerError,
    PokeApiTransportError,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class PokeApiClient:
    """Asynchronous HTTP client for fetching and caching raw PokeAPI payloads."""

    def __init__(
        self,
        base_url: str | None = None,
        cache_dir: Path | str | None = None,
        enable_cache: bool = True,
        timeout: float | None = None,
        max_retries: int | None = None,
        backoff_factor: float | None = None,
        client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or settings.POKEAPI_BASE_URL).rstrip("/")
        self.enable_cache = enable_cache
        self.timeout = timeout if timeout is not None else settings.POKEAPI_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.POKEAPI_MAX_RETRIES
        self.backoff_factor = (
            backoff_factor if backoff_factor is not None else settings.POKEAPI_BACKOFF_FACTOR
        )

        resolved_cache_dir = cache_dir or settings.POKEAPI_CACHE_DIR
        self._cache = PokeApiCache(cache_dir=resolved_cache_dir)

        if client is not None:
            self._client = client
            self._owned_client = False
        else:
            client_base_url = f"{self.base_url}/"
            self._client = httpx.AsyncClient(
                base_url=client_base_url,
                transport=transport,
                timeout=self.timeout,
            )
            self._owned_client = True

    @property
    def cache(self) -> PokeApiCache:
        """Access the underlying raw JSON cache."""
        return self._cache

    @staticmethod
    def normalize_identifier(id_or_name: int | str) -> str:
        """Normalize resource identifier (trim whitespace, lowercase)."""
        if isinstance(id_or_name, int):
            return str(id_or_name)
        normalized = str(id_or_name).strip().lower()
        if not normalized:
            raise ValueError("Resource identifier cannot be empty")
        return normalized

    async def _get(self, endpoint: str, identifier: str) -> dict[str, Any]:
        """Fetch raw JSON for an endpoint and identifier, using cache and retry mechanisms."""
        # 1. Check local cache
        if self.enable_cache:
            cached_payload = self._cache.get(endpoint, identifier)
            if cached_payload is not None:
                return cached_payload

        # 2. HTTP Request with bounded retries
        url_path = f"{endpoint}/{identifier}"
        attempt = 0

        while True:
            attempt += 1
            try:
                response = await self._client.get(url_path)

                if response.status_code == 200:
                    data = response.json()
                    if self.enable_cache and isinstance(data, dict):
                        self._cache.set(endpoint, identifier, data)
                    return data

                if response.status_code == 404:
                    # Permanent client error: do NOT retry
                    raise PokeApiNotFoundError(resource=url_path)

                if response.status_code in (429, 500, 502, 503, 504):
                    if attempt <= self.max_retries:
                        if self.backoff_factor > 0:
                            delay = self.backoff_factor * (2 ** (attempt - 1))
                            await asyncio.sleep(delay)
                        continue

                    if response.status_code == 429:
                        raise PokeApiRateLimitError()
                    raise PokeApiServerError(status_code=response.status_code)

                # Other 4xx or unexpected HTTP status
                response.raise_for_status()

            except httpx.TransportError as exc:
                if attempt <= self.max_retries:
                    if self.backoff_factor > 0:
                        delay = self.backoff_factor * (2 ** (attempt - 1))
                        await asyncio.sleep(delay)
                    continue
                raise PokeApiTransportError(
                    f"Network transport error connecting to PokeAPI: {exc}"
                ) from exc
            except (PokeApiError, ValueError):
                raise
            except httpx.HTTPStatusError as exc:
                raise PokeApiError(
                    f"PokeAPI returned HTTP {exc.response.status_code}: {exc}",
                    status_code=exc.response.status_code,
                ) from exc
            except Exception as exc:
                raise PokeApiError(f"Unexpected error communicating with PokeAPI: {exc}") from exc

    async def get_pokemon(self, id_or_name: int | str) -> dict[str, Any]:
        """Retrieve raw Pokémon data (/pokemon/{id_or_name})."""
        norm_id = self.normalize_identifier(id_or_name)
        return await self._get("pokemon", norm_id)

    async def get_pokemon_species(self, id_or_name: int | str) -> dict[str, Any]:
        """Retrieve raw Pokémon species data (/pokemon-species/{id_or_name})."""
        norm_id = self.normalize_identifier(id_or_name)
        return await self._get("pokemon-species", norm_id)

    async def get_generation(self, id_or_name: int | str) -> dict[str, Any]:
        """Retrieve raw Generation data (/generation/{id_or_name})."""
        norm_id = self.normalize_identifier(id_or_name)
        return await self._get("generation", norm_id)

    async def get_version_group(self, id_or_name: int | str) -> dict[str, Any]:
        """Retrieve raw Version Group data (/version-group/{id_or_name})."""
        norm_id = self.normalize_identifier(id_or_name)
        return await self._get("version-group", norm_id)

    async def close(self) -> None:
        """Close owned HTTP client resources."""
        if self._owned_client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> PokeApiClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        await self.close()
