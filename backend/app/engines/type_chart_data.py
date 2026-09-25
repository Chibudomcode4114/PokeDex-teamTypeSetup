"""Complete Pokémon type-effectiveness charts for supported rule versions.

Separates raw type-chart matrices from matchup calculation logic.
Supports:
- Generation II through V (17 types, Steel resists Ghost/Dark, no Fairy)
- Generation VI+ (18 types, Fairy added, Steel neutral to Ghost/Dark)
"""

from app.engines.rules_engine import GEN_3_SUPPORTED_TYPES, GEN_6_SUPPORTED_TYPES
from app.models.domain import PokemonType, TypeChartVersion

# Base interactions for Generations II through V (17 types)
_GEN_2_TO_5_INTERACTIONS: dict[PokemonType, dict[PokemonType, float]] = {
    PokemonType.NORMAL: {
        PokemonType.ROCK: 0.5,
        PokemonType.STEEL: 0.5,
        PokemonType.GHOST: 0.0,
    },
    PokemonType.FIRE: {
        PokemonType.GRASS: 2.0,
        PokemonType.ICE: 2.0,
        PokemonType.BUG: 2.0,
        PokemonType.STEEL: 2.0,
        PokemonType.FIRE: 0.5,
        PokemonType.WATER: 0.5,
        PokemonType.ROCK: 0.5,
        PokemonType.DRAGON: 0.5,
    },
    PokemonType.WATER: {
        PokemonType.FIRE: 2.0,
        PokemonType.GROUND: 2.0,
        PokemonType.ROCK: 2.0,
        PokemonType.WATER: 0.5,
        PokemonType.GRASS: 0.5,
        PokemonType.DRAGON: 0.5,
    },
    PokemonType.ELECTRIC: {
        PokemonType.WATER: 2.0,
        PokemonType.FLYING: 2.0,
        PokemonType.ELECTRIC: 0.5,
        PokemonType.GRASS: 0.5,
        PokemonType.DRAGON: 0.5,
        PokemonType.GROUND: 0.0,
    },
    PokemonType.GRASS: {
        PokemonType.WATER: 2.0,
        PokemonType.GROUND: 2.0,
        PokemonType.ROCK: 2.0,
        PokemonType.FIRE: 0.5,
        PokemonType.GRASS: 0.5,
        PokemonType.POISON: 0.5,
        PokemonType.FLYING: 0.5,
        PokemonType.BUG: 0.5,
        PokemonType.DRAGON: 0.5,
        PokemonType.STEEL: 0.5,
    },
    PokemonType.ICE: {
        PokemonType.GRASS: 2.0,
        PokemonType.GROUND: 2.0,
        PokemonType.FLYING: 2.0,
        PokemonType.DRAGON: 2.0,
        PokemonType.FIRE: 0.5,
        PokemonType.WATER: 0.5,
        PokemonType.ICE: 0.5,
        PokemonType.STEEL: 0.5,
    },
    PokemonType.FIGHTING: {
        PokemonType.NORMAL: 2.0,
        PokemonType.ICE: 2.0,
        PokemonType.ROCK: 2.0,
        PokemonType.DARK: 2.0,
        PokemonType.STEEL: 2.0,
        PokemonType.POISON: 0.5,
        PokemonType.FLYING: 0.5,
        PokemonType.PSYCHIC: 0.5,
        PokemonType.BUG: 0.5,
        PokemonType.GHOST: 0.0,
    },
    PokemonType.POISON: {
        PokemonType.GRASS: 2.0,
        PokemonType.POISON: 0.5,
        PokemonType.GROUND: 0.5,
        PokemonType.ROCK: 0.5,
        PokemonType.GHOST: 0.5,
        PokemonType.STEEL: 0.0,
    },
    PokemonType.GROUND: {
        PokemonType.FIRE: 2.0,
        PokemonType.ELECTRIC: 2.0,
        PokemonType.POISON: 2.0,
        PokemonType.ROCK: 2.0,
        PokemonType.STEEL: 2.0,
        PokemonType.GRASS: 0.5,
        PokemonType.BUG: 0.5,
        PokemonType.FLYING: 0.0,
    },
    PokemonType.FLYING: {
        PokemonType.GRASS: 2.0,
        PokemonType.FIGHTING: 2.0,
        PokemonType.BUG: 2.0,
        PokemonType.ELECTRIC: 0.5,
        PokemonType.ROCK: 0.5,
        PokemonType.STEEL: 0.5,
    },
    PokemonType.PSYCHIC: {
        PokemonType.FIGHTING: 2.0,
        PokemonType.POISON: 2.0,
        PokemonType.PSYCHIC: 0.5,
        PokemonType.STEEL: 0.5,
        PokemonType.DARK: 0.0,
    },
    PokemonType.BUG: {
        PokemonType.GRASS: 2.0,
        PokemonType.PSYCHIC: 2.0,
        PokemonType.DARK: 2.0,
        PokemonType.FIRE: 0.5,
        PokemonType.FIGHTING: 0.5,
        PokemonType.POISON: 0.5,
        PokemonType.FLYING: 0.5,
        PokemonType.GHOST: 0.5,
        PokemonType.STEEL: 0.5,
    },
    PokemonType.ROCK: {
        PokemonType.FIRE: 2.0,
        PokemonType.ICE: 2.0,
        PokemonType.FLYING: 2.0,
        PokemonType.BUG: 2.0,
        PokemonType.FIGHTING: 0.5,
        PokemonType.GROUND: 0.5,
        PokemonType.STEEL: 0.5,
    },
    PokemonType.GHOST: {
        PokemonType.PSYCHIC: 2.0,
        PokemonType.GHOST: 2.0,
        PokemonType.STEEL: 0.5,  # In Gen 2-5, Steel resists Ghost
        PokemonType.NORMAL: 0.0,
    },
    PokemonType.DRAGON: {
        PokemonType.DRAGON: 2.0,
        PokemonType.STEEL: 0.5,
    },
    PokemonType.STEEL: {
        PokemonType.ICE: 2.0,
        PokemonType.ROCK: 2.0,
        PokemonType.FIRE: 0.5,
        PokemonType.WATER: 0.5,
        PokemonType.ELECTRIC: 0.5,
        PokemonType.STEEL: 0.5,
    },
    PokemonType.DARK: {
        PokemonType.PSYCHIC: 2.0,
        PokemonType.GHOST: 2.0,
        PokemonType.FIGHTING: 0.5,
        PokemonType.DARK: 0.5,
        PokemonType.STEEL: 0.5,  # In Gen 2-5, Steel resists Dark
    },
}

# Base interactions for Generation VI+ (18 types)
_GEN_6_PLUS_INTERACTIONS: dict[PokemonType, dict[PokemonType, float]] = {
    PokemonType.NORMAL: {
        PokemonType.ROCK: 0.5,
        PokemonType.STEEL: 0.5,
        PokemonType.GHOST: 0.0,
    },
    PokemonType.FIRE: {
        PokemonType.GRASS: 2.0,
        PokemonType.ICE: 2.0,
        PokemonType.BUG: 2.0,
        PokemonType.STEEL: 2.0,
        PokemonType.FIRE: 0.5,
        PokemonType.WATER: 0.5,
        PokemonType.ROCK: 0.5,
        PokemonType.DRAGON: 0.5,
    },
    PokemonType.WATER: {
        PokemonType.FIRE: 2.0,
        PokemonType.GROUND: 2.0,
        PokemonType.ROCK: 2.0,
        PokemonType.WATER: 0.5,
        PokemonType.GRASS: 0.5,
        PokemonType.DRAGON: 0.5,
    },
    PokemonType.ELECTRIC: {
        PokemonType.WATER: 2.0,
        PokemonType.FLYING: 2.0,
        PokemonType.ELECTRIC: 0.5,
        PokemonType.GRASS: 0.5,
        PokemonType.DRAGON: 0.5,
        PokemonType.GROUND: 0.0,
    },
    PokemonType.GRASS: {
        PokemonType.WATER: 2.0,
        PokemonType.GROUND: 2.0,
        PokemonType.ROCK: 2.0,
        PokemonType.FIRE: 0.5,
        PokemonType.GRASS: 0.5,
        PokemonType.POISON: 0.5,
        PokemonType.FLYING: 0.5,
        PokemonType.BUG: 0.5,
        PokemonType.DRAGON: 0.5,
        PokemonType.STEEL: 0.5,
    },
    PokemonType.ICE: {
        PokemonType.GRASS: 2.0,
        PokemonType.GROUND: 2.0,
        PokemonType.FLYING: 2.0,
        PokemonType.DRAGON: 2.0,
        PokemonType.FIRE: 0.5,
        PokemonType.WATER: 0.5,
        PokemonType.ICE: 0.5,
        PokemonType.STEEL: 0.5,
    },
    PokemonType.FIGHTING: {
        PokemonType.NORMAL: 2.0,
        PokemonType.ICE: 2.0,
        PokemonType.ROCK: 2.0,
        PokemonType.DARK: 2.0,
        PokemonType.STEEL: 2.0,
        PokemonType.POISON: 0.5,
        PokemonType.FLYING: 0.5,
        PokemonType.PSYCHIC: 0.5,
        PokemonType.BUG: 0.5,
        PokemonType.FAIRY: 0.5,  # Fairy resists Fighting
        PokemonType.GHOST: 0.0,
    },
    PokemonType.POISON: {
        PokemonType.GRASS: 2.0,
        PokemonType.FAIRY: 2.0,  # Fairy is weak to Poison
        PokemonType.POISON: 0.5,
        PokemonType.GROUND: 0.5,
        PokemonType.ROCK: 0.5,
        PokemonType.GHOST: 0.5,
        PokemonType.STEEL: 0.0,
    },
    PokemonType.GROUND: {
        PokemonType.FIRE: 2.0,
        PokemonType.ELECTRIC: 2.0,
        PokemonType.POISON: 2.0,
        PokemonType.ROCK: 2.0,
        PokemonType.STEEL: 2.0,
        PokemonType.GRASS: 0.5,
        PokemonType.BUG: 0.5,
        PokemonType.FLYING: 0.0,
    },
    PokemonType.FLYING: {
        PokemonType.GRASS: 2.0,
        PokemonType.FIGHTING: 2.0,
        PokemonType.BUG: 2.0,
        PokemonType.ELECTRIC: 0.5,
        PokemonType.ROCK: 0.5,
        PokemonType.STEEL: 0.5,
    },
    PokemonType.PSYCHIC: {
        PokemonType.FIGHTING: 2.0,
        PokemonType.POISON: 2.0,
        PokemonType.PSYCHIC: 0.5,
        PokemonType.STEEL: 0.5,
        PokemonType.DARK: 0.0,
    },
    PokemonType.BUG: {
        PokemonType.GRASS: 2.0,
        PokemonType.PSYCHIC: 2.0,
        PokemonType.DARK: 2.0,
        PokemonType.FIRE: 0.5,
        PokemonType.FIGHTING: 0.5,
        PokemonType.POISON: 0.5,
        PokemonType.FLYING: 0.5,
        PokemonType.GHOST: 0.5,
        PokemonType.STEEL: 0.5,
        PokemonType.FAIRY: 0.5,  # Fairy resists Bug
    },
    PokemonType.ROCK: {
        PokemonType.FIRE: 2.0,
        PokemonType.ICE: 2.0,
        PokemonType.FLYING: 2.0,
        PokemonType.BUG: 2.0,
        PokemonType.FIGHTING: 0.5,
        PokemonType.GROUND: 0.5,
        PokemonType.STEEL: 0.5,
    },
    PokemonType.GHOST: {
        PokemonType.PSYCHIC: 2.0,
        PokemonType.GHOST: 2.0,
        # Note: In Gen 6+, Steel is neutral (1.0) to Ghost
        PokemonType.NORMAL: 0.0,
    },
    PokemonType.DRAGON: {
        PokemonType.DRAGON: 2.0,
        PokemonType.STEEL: 0.5,
        PokemonType.FAIRY: 0.0,  # Fairy is immune to Dragon
    },
    PokemonType.STEEL: {
        PokemonType.ICE: 2.0,
        PokemonType.ROCK: 2.0,
        PokemonType.FAIRY: 2.0,  # Fairy is weak to Steel
        PokemonType.FIRE: 0.5,
        PokemonType.WATER: 0.5,
        PokemonType.ELECTRIC: 0.5,
        PokemonType.STEEL: 0.5,
    },
    PokemonType.DARK: {
        PokemonType.PSYCHIC: 2.0,
        PokemonType.GHOST: 2.0,
        PokemonType.FIGHTING: 0.5,
        PokemonType.DARK: 0.5,
        PokemonType.FAIRY: 0.5,  # Fairy resists Dark
        # Note: In Gen 6+, Steel is neutral (1.0) to Dark
    },
    PokemonType.FAIRY: {
        PokemonType.FIGHTING: 2.0,
        PokemonType.DRAGON: 2.0,
        PokemonType.DARK: 2.0,
        PokemonType.FIRE: 0.5,
        PokemonType.POISON: 0.5,
        PokemonType.STEEL: 0.5,
    },
}


def _build_complete_matrix(
    supported_types: tuple[PokemonType, ...],
    interactions: dict[PokemonType, dict[PokemonType, float]],
) -> dict[tuple[PokemonType, PokemonType], float]:
    """Build a complete dense (attacking, defending) -> multiplier lookup matrix."""
    matrix: dict[tuple[PokemonType, PokemonType], float] = {}
    for attacking in supported_types:
        atk_overrides = interactions.get(attacking, {})
        for defending in supported_types:
            matrix[(attacking, defending)] = atk_overrides.get(defending, 1.0)
    return matrix


# Complete precomputed matrices
GEN_2_TO_5_MATRIX: dict[tuple[PokemonType, PokemonType], float] = _build_complete_matrix(
    GEN_3_SUPPORTED_TYPES, _GEN_2_TO_5_INTERACTIONS
)

GEN_6_PLUS_MATRIX: dict[tuple[PokemonType, PokemonType], float] = _build_complete_matrix(
    GEN_6_SUPPORTED_TYPES, _GEN_6_PLUS_INTERACTIONS
)

# Registry mapping version to (matrix, supported_types)
TYPE_CHARTS: dict[
    TypeChartVersion, tuple[dict[tuple[PokemonType, PokemonType], float], tuple[PokemonType, ...]]
] = {
    TypeChartVersion.GEN_2_TO_5: (GEN_2_TO_5_MATRIX, GEN_3_SUPPORTED_TYPES),
    TypeChartVersion.GEN_6_PLUS: (GEN_6_PLUS_MATRIX, GEN_6_SUPPORTED_TYPES),
}
