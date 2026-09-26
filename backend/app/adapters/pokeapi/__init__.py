"""PokeAPI external adapter and normalization package (Milestone 2)."""

from app.adapters.pokeapi.cache import PokeApiCache
from app.adapters.pokeapi.client import PokeApiClient
from app.adapters.pokeapi.exceptions import (
    PokeApiError,
    PokeApiNormalizationError,
    PokeApiNotFoundError,
    PokeApiRateLimitError,
    PokeApiServerError,
    PokeApiTransportError,
)
from app.adapters.pokeapi.normalizer import PokeApiNormalizer
from app.adapters.pokeapi.schemas import (
    NormalizedAbilityAssignment,
    NormalizedBaseStats,
    NormalizedPokemon,
    NormalizedTypeAssignment,
    TargetGameContext,
    get_target_game_context,
)

__all__ = [
    "NormalizedAbilityAssignment",
    "NormalizedBaseStats",
    "NormalizedPokemon",
    "NormalizedTypeAssignment",
    "PokeApiCache",
    "PokeApiClient",
    "PokeApiError",
    "PokeApiNormalizationError",
    "PokeApiNotFoundError",
    "PokeApiNormalizer",
    "PokeApiRateLimitError",
    "PokeApiServerError",
    "PokeApiTransportError",
    "TargetGameContext",
    "get_target_game_context",
]
