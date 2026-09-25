"""Game Rules Engine for resolving game-specific rule profiles.

This engine is completely decoupled from UI, databases, and network adapters.
It enforces fail-closed behavior: unsupported games raise GameNotFoundError
and will never silently fall back to another generation.
"""

from app.core.errors import GameNotFoundError
from app.models.domain import (
    GameRuleProfile,
    Generation,
    MechanicFlags,
    PhysicalSpecialModel,
    PokemonType,
    TypeChartVersion,
)

# Standard 17 elemental types present in Generations II through V
GEN_3_SUPPORTED_TYPES: tuple[PokemonType, ...] = (
    PokemonType.NORMAL,
    PokemonType.FIRE,
    PokemonType.WATER,
    PokemonType.ELECTRIC,
    PokemonType.GRASS,
    PokemonType.ICE,
    PokemonType.FIGHTING,
    PokemonType.POISON,
    PokemonType.GROUND,
    PokemonType.FLYING,
    PokemonType.PSYCHIC,
    PokemonType.BUG,
    PokemonType.ROCK,
    PokemonType.GHOST,
    PokemonType.DRAGON,
    PokemonType.STEEL,
    PokemonType.DARK,
)

# Standard 18 elemental types present in Generation VI+ (includes Fairy)
GEN_6_SUPPORTED_TYPES: tuple[PokemonType, ...] = (
    *GEN_3_SUPPORTED_TYPES,
    PokemonType.FAIRY,
)

# Canonical rule profiles for MVP supported games
_FIRERED_PROFILE = GameRuleProfile(
    game_id="firered",
    game_title="Pokémon FireRed",
    generation=Generation.GEN_3,
    type_chart_version=TypeChartVersion.GEN_2_TO_5,
    physical_special_model=PhysicalSpecialModel.BY_TYPE,
    supported_types=GEN_3_SUPPORTED_TYPES,
    mechanic_flags=MechanicFlags(
        has_fairy_type=False,
        steel_resists_dark_ghost=True,
        physical_special_split=False,
        has_abilities=True,
    ),
)

_LEAFGREEN_PROFILE = GameRuleProfile(
    game_id="leafgreen",
    game_title="Pokémon LeafGreen",
    generation=Generation.GEN_3,
    type_chart_version=TypeChartVersion.GEN_2_TO_5,
    physical_special_model=PhysicalSpecialModel.BY_TYPE,
    supported_types=GEN_3_SUPPORTED_TYPES,
    mechanic_flags=MechanicFlags(
        has_fairy_type=False,
        steel_resists_dark_ghost=True,
        physical_special_split=False,
        has_abilities=True,
    ),
)

_POKEMON_X_PROFILE = GameRuleProfile(
    game_id="pokemon_x",
    game_title="Pokémon X",
    generation=Generation.GEN_6,
    type_chart_version=TypeChartVersion.GEN_6_PLUS,
    physical_special_model=PhysicalSpecialModel.BY_MOVE,
    supported_types=GEN_6_SUPPORTED_TYPES,
    mechanic_flags=MechanicFlags(
        has_fairy_type=True,
        steel_resists_dark_ghost=False,
        physical_special_split=True,
        has_abilities=True,
    ),
)

_POKEMON_Y_PROFILE = GameRuleProfile(
    game_id="pokemon_y",
    game_title="Pokémon Y",
    generation=Generation.GEN_6,
    type_chart_version=TypeChartVersion.GEN_6_PLUS,
    physical_special_model=PhysicalSpecialModel.BY_MOVE,
    supported_types=GEN_6_SUPPORTED_TYPES,
    mechanic_flags=MechanicFlags(
        has_fairy_type=True,
        steel_resists_dark_ghost=False,
        physical_special_split=True,
        has_abilities=True,
    ),
)


class GameRulesEngine:
    """Pure domain engine that maps game identifiers to their resolved rule profiles."""

    def __init__(self) -> None:
        self._profiles: dict[str, GameRuleProfile] = {
            "firered": _FIRERED_PROFILE,
            "leafgreen": _LEAFGREEN_PROFILE,
            "pokemon_x": _POKEMON_X_PROFILE,
            "pokemon_y": _POKEMON_Y_PROFILE,
        }
        # Normalized alias mappings
        self._aliases: dict[str, str] = {
            "pokemon-firered": "firered",
            "pokemon_firered": "firered",
            "pokemon-leafgreen": "leafgreen",
            "pokemon_leafgreen": "leafgreen",
            "x": "pokemon_x",
            "pokemon-x": "pokemon_x",
            "y": "pokemon_y",
            "pokemon-y": "pokemon_y",
        }

    def resolve(self, game_id: str) -> GameRuleProfile:
        """Resolve the rule profile for a game.

        Args:
            game_id: The unique identifier or alias of the Pokémon game.

        Returns:
            The resolved GameRuleProfile.

        Raises:
            GameNotFoundError: If the game is unsupported or invalid.
        """
        normalized_id = game_id.strip().lower()
        canonical_id = self._aliases.get(normalized_id, normalized_id)

        profile = self._profiles.get(canonical_id)
        if profile is None:
            raise GameNotFoundError(game_id)

        return profile

    def get_rule_profile(self, game_id: str) -> GameRuleProfile:
        """Alias for resolve() to support multiple naming conventions."""
        return self.resolve(game_id)

    def is_game_supported(self, game_id: str) -> bool:
        """Check whether a game identifier is supported."""
        try:
            self.resolve(game_id)
            return True
        except GameNotFoundError:
            return False

    def get_supported_game_ids(self) -> list[str]:
        """Return the canonical list of supported game IDs."""
        return list(self._profiles.keys())


# Global default instance
rules_engine = GameRulesEngine()
