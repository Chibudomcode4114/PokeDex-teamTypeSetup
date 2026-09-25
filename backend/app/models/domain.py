"""Pure domain models for game contexts, rule profiles, and type systems.

This module is strictly decoupled from frameworks, databases, and network adapters.
"""

from dataclasses import dataclass
from enum import IntEnum, StrEnum

VALID_DEFENSIVE_MULTIPLIERS: tuple[float, ...] = (0.0, 0.25, 0.5, 1.0, 2.0, 4.0)


class PokemonType(StrEnum):
    """Enumeration of all Pokémon elemental types across all generations."""

    NORMAL = "normal"
    FIRE = "fire"
    WATER = "water"
    ELECTRIC = "electric"
    GRASS = "grass"
    ICE = "ice"
    FIGHTING = "fighting"
    POISON = "poison"
    GROUND = "ground"
    FLYING = "flying"
    PSYCHIC = "psychic"
    BUG = "bug"
    ROCK = "rock"
    GHOST = "ghost"
    DRAGON = "dragon"
    STEEL = "steel"
    DARK = "dark"
    FAIRY = "fairy"


class Generation(IntEnum):
    """Pokémon game generation numbering."""

    GEN_1 = 1
    GEN_2 = 2
    GEN_3 = 3
    GEN_4 = 4
    GEN_5 = 5
    GEN_6 = 6
    GEN_7 = 7
    GEN_8 = 8
    GEN_9 = 9


class TypeChartVersion(StrEnum):
    """Type chart rule versions representing generational rule changes."""

    GEN_1 = "gen1"
    GEN_2_TO_5 = "gen2_5"
    GEN_6_PLUS = "gen6_plus"


class PhysicalSpecialModel(StrEnum):
    """Model used to determine physical vs special damage categorization."""

    BY_TYPE = "by_type"  # Gen 1-3: type determines physical/special
    BY_MOVE = "by_move"  # Gen 4+: individual move determines category


@dataclass(frozen=True)
class MechanicFlags:
    """Feature and rule flags for a specific Pokémon game."""

    has_fairy_type: bool
    steel_resists_dark_ghost: bool
    physical_special_split: bool
    has_abilities: bool


@dataclass(frozen=True)
class GameRuleProfile:
    """Resolved rule profile governing game mechanics and valid Pokémon data."""

    game_id: str
    game_title: str
    generation: Generation
    type_chart_version: TypeChartVersion
    physical_special_model: PhysicalSpecialModel
    supported_types: tuple[PokemonType, ...]
    mechanic_flags: MechanicFlags

    def is_type_supported(self, pokemon_type: PokemonType | str) -> bool:
        """Check if an elemental type exists in this game's rule context."""
        if isinstance(pokemon_type, str):
            try:
                pokemon_type = PokemonType(pokemon_type.lower())
            except ValueError:
                return False
        return pokemon_type in self.supported_types


@dataclass(frozen=True)
class TypeMatchupResult:
    """Calculated defensive type matchup result."""

    attacking_type: PokemonType
    defending_types: tuple[PokemonType, ...]
    multiplier: float
    chart_version: TypeChartVersion
