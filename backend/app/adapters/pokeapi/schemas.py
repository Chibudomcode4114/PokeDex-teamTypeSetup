"""Normalized data contracts and game context definitions for PokeAPI data."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetGameContext:
    """Target game context for normalizing PokeAPI payloads."""

    game_id: str
    generation: int
    version_name: str  # PokeAPI internal version slug used in game_indices
    version_group: str


# Supported MVP target game contexts
SUPPORTED_TARGET_GAMES: dict[str, TargetGameContext] = {
    "firered": TargetGameContext(
        game_id="firered",
        generation=3,
        version_name="firered",
        version_group="firered-leafgreen",
    ),
    "leafgreen": TargetGameContext(
        game_id="leafgreen",
        generation=3,
        version_name="leafgreen",
        version_group="firered-leafgreen",
    ),
    "pokemon-x": TargetGameContext(
        game_id="pokemon-x",
        generation=6,
        version_name="x",
        version_group="x-y",
    ),
    "x": TargetGameContext(
        game_id="pokemon-x",
        generation=6,
        version_name="x",
        version_group="x-y",
    ),
    "pokemon-y": TargetGameContext(
        game_id="pokemon-y",
        generation=6,
        version_name="y",
        version_group="x-y",
    ),
    "y": TargetGameContext(
        game_id="pokemon-y",
        generation=6,
        version_name="y",
        version_group="x-y",
    ),
}


def get_target_game_context(game_id: str) -> TargetGameContext:
    """Resolve a target game context by game ID or alias."""
    normalized_id = game_id.strip().lower()
    context = SUPPORTED_TARGET_GAMES.get(normalized_id)
    if context is None:
        raise ValueError(
            f"Unsupported target game: '{game_id}'. Supported games: "
            f"{sorted(set(g.game_id for g in SUPPORTED_TARGET_GAMES.values()))}"
        )
    return context


@dataclass(frozen=True)
class NormalizedTypeAssignment:
    """Game-specific elemental type assignment."""

    slot: int
    type_id: str


@dataclass(frozen=True)
class NormalizedAbilityAssignment:
    """Game-specific ability assignment."""

    slot: int
    ability_id: str
    is_hidden: bool


@dataclass(frozen=True)
class NormalizedBaseStats:
    """Game-specific six battle base stats."""

    hp: int
    atk: int
    def_: int
    spa: int
    spd: int
    spe: int


@dataclass(frozen=True)
class NormalizedPokemon:
    """Normalized, game-specific Pokémon entity ready for database ingestion."""

    id: str
    dex_number: int
    name: str
    slug: str
    species_name: str
    form_name: str | None
    is_default: bool
    game_id: str
    is_available: bool
    types: tuple[NormalizedTypeAssignment, ...]
    abilities: tuple[NormalizedAbilityAssignment, ...]
    base_stats: NormalizedBaseStats
