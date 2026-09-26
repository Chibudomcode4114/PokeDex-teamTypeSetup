"""Unit tests for PokeApiClient and PokeApiCache.

All tests operate offline using httpx.MockTransport and temporary file directories.
Zero requests are sent to the live internet.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.adapters.pokeapi.client import PokeApiClient
from app.adapters.pokeapi.exceptions import (
    PokeApiError,
    PokeApiNotFoundError,
    PokeApiRateLimitError,
    PokeApiServerError,
    PokeApiTransportError,
)


@pytest.mark.asyncio
class TestPokeApiClient:
    """Test suite verifying endpoint construction, caching, retries, and error boundaries."""

    async def test_endpoint_paths_and_normalization(self, tmp_path: Path) -> None:
        """Verify endpoint path construction and input normalization."""
        recorded_paths: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            recorded_paths.append(request.url.path)
            return httpx.Response(200, json={"id": 1, "name": "mock"})

        transport = httpx.MockTransport(handler)
        async with PokeApiClient(
            transport=transport, cache_dir=tmp_path, backoff_factor=0.0
        ) as client:
            # 1. Pokemon endpoint + uppercase/whitespace normalization
            res_poke = await client.get_pokemon("  Pikachu  ")
            assert res_poke["name"] == "mock"
            assert recorded_paths[-1] == "/api/v2/pokemon/pikachu"

            # 2. Pokemon species endpoint + integer normalization
            await client.get_pokemon_species(25)
            assert recorded_paths[-1] == "/api/v2/pokemon-species/25"

            # 3. Generation endpoint
            await client.get_generation("GENERATION-iii")
            assert recorded_paths[-1] == "/api/v2/generation/generation-iii"

            # 4. Version group endpoint
            await client.get_version_group("FireRed-LeafGreen")
            assert recorded_paths[-1] == "/api/v2/version-group/firered-leafgreen"

            # 5. Empty identifier rejection
            with pytest.raises(ValueError, match="cannot be empty"):
                await client.get_pokemon("   ")

    async def test_successful_response_and_caching(self, tmp_path: Path) -> None:
        """Verify successful response is returned, cached, and subsequent request uses cache."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json={"id": 25, "name": "pikachu", "types": ["electric"]})

        transport = httpx.MockTransport(handler)
        async with PokeApiClient(
            transport=transport, cache_dir=tmp_path, backoff_factor=0.0
        ) as client:
            # First request: network call
            data1 = await client.get_pokemon("pikachu")
            assert call_count == 1
            assert data1["id"] == 25
            assert data1["name"] == "pikachu"

            # Verify file exists on disk
            cache_file = tmp_path / "pokemon" / "pikachu.json"
            assert cache_file.is_file()

            # Second request: served from cache, network NOT called
            data2 = await client.get_pokemon("Pikachu")
            assert call_count == 1  # Still 1!
            assert data2 == data1

    async def test_corrupted_cache_entry_ignored_and_refetched(self, tmp_path: Path) -> None:
        """Verify corrupted cache files are safely ignored and data is refetched from network."""
        # Pre-seed corrupted file
        cache_file = tmp_path / "pokemon" / "pikachu.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("{corrupted-raw-json-data!!", encoding="utf-8")

        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json={"id": 25, "name": "pikachu"})

        transport = httpx.MockTransport(handler)
        async with PokeApiClient(
            transport=transport, cache_dir=tmp_path, backoff_factor=0.0
        ) as client:
            data = await client.get_pokemon("pikachu")
            assert call_count == 1
            assert data["name"] == "pikachu"

            # Cache file should now be overwritten with valid JSON
            with open(cache_file, encoding="utf-8") as f:
                refreshed = json.load(f)
            assert refreshed["id"] == 25

    async def test_404_not_retried(self, tmp_path: Path) -> None:
        """Verify 404 response immediately raises PokeApiNotFoundError without retrying."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(404, text="Not Found")

        transport = httpx.MockTransport(handler)
        async with PokeApiClient(
            transport=transport, cache_dir=tmp_path, max_retries=3, backoff_factor=0.0
        ) as client:
            with pytest.raises(PokeApiNotFoundError) as exc_info:
                await client.get_pokemon("missing-mon")

            assert exc_info.value.status_code == 404
            assert "pokemon/missing-mon" in exc_info.value.resource
            assert call_count == 1  # Crucial: exactly 1 call, zero retries

    async def test_transient_5xx_retried_and_succeeds(self, tmp_path: Path) -> None:
        """Verify transient 5xx server errors are retried within limit and succeed."""
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return httpx.Response(500, text="Internal Error")
            if attempts == 2:
                return httpx.Response(502, text="Bad Gateway")
            return httpx.Response(200, json={"id": 1, "name": "bulbasaur"})

        transport = httpx.MockTransport(handler)
        async with PokeApiClient(
            transport=transport, cache_dir=tmp_path, max_retries=3, backoff_factor=0.0
        ) as client:
            data = await client.get_pokemon("bulbasaur")
            assert data["name"] == "bulbasaur"
            assert attempts == 3

    async def test_transient_5xx_retry_limit_exhausted(self, tmp_path: Path) -> None:
        """Verify repeated 5xx errors exhaust retries and raise PokeApiServerError."""
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(503, text="Service Unavailable")

        transport = httpx.MockTransport(handler)
        async with PokeApiClient(
            transport=transport, cache_dir=tmp_path, max_retries=2, backoff_factor=0.0
        ) as client:
            with pytest.raises(PokeApiServerError) as exc_info:
                await client.get_pokemon("charmander")

            assert exc_info.value.status_code == 503
            assert attempts == 3  # 1 initial attempt + 2 retries

    async def test_transient_429_retried_and_exhausted(self, tmp_path: Path) -> None:
        """Verify 429 rate limit errors are retried and raise PokeApiRateLimitError if exhausted."""
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(429, text="Too Many Requests")

        transport = httpx.MockTransport(handler)
        async with PokeApiClient(
            transport=transport, cache_dir=tmp_path, max_retries=2, backoff_factor=0.0
        ) as client:
            with pytest.raises(PokeApiRateLimitError) as exc_info:
                await client.get_pokemon("squirtle")

            assert exc_info.value.status_code == 429
            assert attempts == 3

    async def test_transport_error_retried_and_succeeds(self, tmp_path: Path) -> None:
        """Verify network transport errors (e.g. timeout, connection dropped) are retried."""
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts <= 2:
                raise httpx.ConnectError("Connection refused by host", request=request)
            return httpx.Response(200, json={"id": 7, "name": "squirtle"})

        transport = httpx.MockTransport(handler)
        async with PokeApiClient(
            transport=transport, cache_dir=tmp_path, max_retries=3, backoff_factor=0.0
        ) as client:
            data = await client.get_pokemon("squirtle")
            assert data["name"] == "squirtle"
            assert attempts == 3

    async def test_transport_error_exhausts_and_raises(self, tmp_path: Path) -> None:
        """Verify persistent network transport errors raise PokeApiTransportError."""
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            raise httpx.ReadTimeout("Socket read timed out", request=request)

        transport = httpx.MockTransport(handler)
        async with PokeApiClient(
            transport=transport, cache_dir=tmp_path, max_retries=2, backoff_factor=0.0
        ) as client:
            with pytest.raises(PokeApiTransportError):
                await client.get_pokemon("squirtle")

            assert attempts == 3

    async def test_client_resources_close_correctly(self, tmp_path: Path) -> None:
        """Verify client cleanly closes underlying httpx client when exiting async context."""
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
        client = PokeApiClient(transport=transport, cache_dir=tmp_path)

        assert client._client.is_closed is False
        await client.close()
        assert client._client.is_closed is True

    async def test_cache_disabled_mode(self, tmp_path: Path) -> None:
        """Verify caching can be explicitly disabled."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json={"name": "ditto"})

        transport = httpx.MockTransport(handler)
        async with PokeApiClient(
            transport=transport, cache_dir=tmp_path, enable_cache=False, backoff_factor=0.0
        ) as client:
            await client.get_pokemon("ditto")
            await client.get_pokemon("ditto")
            assert call_count == 2
            assert not (tmp_path / "pokemon" / "ditto.json").exists()

    async def test_other_client_errors_not_retried(self, tmp_path: Path) -> None:
        """Verify permanent client errors (e.g. 400 Bad Request, 403 Forbidden) are not retried."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(400, text="Bad Request")

        transport = httpx.MockTransport(handler)
        async with PokeApiClient(
            transport=transport, cache_dir=tmp_path, max_retries=3, backoff_factor=0.0
        ) as client:
            with pytest.raises(PokeApiError) as exc_info:
                await client.get_pokemon("bad-request")

            assert exc_info.value.status_code == 400
            assert call_count == 1
