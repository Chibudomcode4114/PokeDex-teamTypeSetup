"""PokeAPI external adapter and normalization package (Milestone 2)."""

from app.adapters.pokeapi.cache import PokeApiCache
from app.adapters.pokeapi.client import PokeApiClient
from app.adapters.pokeapi.exceptions import (
    PokeApiError,
    PokeApiNotFoundError,
    PokeApiRateLimitError,
    PokeApiServerError,
    PokeApiTransportError,
)

__all__ = [
    "PokeApiCache",
    "PokeApiClient",
    "PokeApiError",
    "PokeApiNotFoundError",
    "PokeApiRateLimitError",
    "PokeApiServerError",
    "PokeApiTransportError",
]
