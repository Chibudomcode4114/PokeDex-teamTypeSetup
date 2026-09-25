"""Pure Type Matchup Engine.

Calculates single-type and dual-type defensive effectiveness based on a
strictly resolved TypeChartVersion or GameRuleProfile.

Zero dependencies on FastAPI, SQLAlchemy, HTTP, databases, or UI.
"""

from collections.abc import Sequence

from app.core.errors import InvalidTypeMatchupError, UnsupportedTypeError
from app.engines.type_chart_data import TYPE_CHARTS
from app.models.domain import (
    GameRuleProfile,
    PokemonType,
    TypeChartVersion,
    TypeMatchupResult,
)


def _normalize_type(t: PokemonType | str) -> PokemonType:
    """Normalize a string or PokemonType into a valid PokemonType enum."""
    if isinstance(t, PokemonType):
        return t
    if isinstance(t, str):
        cleaned = t.strip().lower()
        try:
            return PokemonType(cleaned)
        except ValueError:
            raise UnsupportedTypeError(f"Invalid Pokemon type: '{t}'.") from None
    raise UnsupportedTypeError(f"Expected PokemonType or str, got {type(t).__name__}.")


def _resolve_chart_version(
    context: TypeChartVersion | GameRuleProfile | str,
) -> TypeChartVersion:
    """Extract and validate the TypeChartVersion from context."""
    if isinstance(context, GameRuleProfile):
        return context.type_chart_version
    if isinstance(context, TypeChartVersion):
        return context
    if isinstance(context, str):
        cleaned = context.strip().lower()
        try:
            return TypeChartVersion(cleaned)
        except ValueError:
            raise UnsupportedTypeError(
                f"Unsupported type chart version: '{context}'."
            ) from None
    raise UnsupportedTypeError(f"Invalid chart context: {type(context).__name__}.")


class TypeMatchupEngine:
    """Pure domain engine for type-vs-type defensive matchup calculations."""

    def calculate_single_matchup(
        self,
        attacking_type: PokemonType | str,
        defending_type: PokemonType | str,
        chart_context: TypeChartVersion | GameRuleProfile | str,
    ) -> float:
        """Calculate the defensive damage multiplier for a single defending type.

        Args:
            attacking_type: The elemental type of the incoming attack.
            defending_type: The elemental type of the defending Pokémon.
            chart_context: The TypeChartVersion or GameRuleProfile specifying the rules.

        Returns:
            Defensive multiplier (0.0, 0.5, 1.0, or 2.0).
        """
        atk = _normalize_type(attacking_type)
        dfn = _normalize_type(defending_type)
        chart_version = _resolve_chart_version(chart_context)

        chart_entry = TYPE_CHARTS.get(chart_version)
        if not chart_entry:
            raise UnsupportedTypeError(
                f"Type chart version '{chart_version.value}' is not configured."
            )

        matrix, supported_types = chart_entry

        if atk not in supported_types:
            raise UnsupportedTypeError(
                f"Type '{atk.value}' is not supported in type chart '{chart_version.value}'."
            )
        if dfn not in supported_types:
            raise UnsupportedTypeError(
                f"Type '{dfn.value}' is not supported in type chart '{chart_version.value}'."
            )

        return matrix[(atk, dfn)]

    def calculate_matchup(
        self,
        attacking_type: PokemonType | str,
        defending_types: PokemonType | str | Sequence[PokemonType | str],
        chart_context: TypeChartVersion | GameRuleProfile | str,
    ) -> float:
        """Calculate the combined defensive multiplier for single or dual defending types.

        Args:
            attacking_type: The elemental type of the incoming attack.
            defending_types: One or two defending elemental types.
            chart_context: The TypeChartVersion or GameRuleProfile specifying the rules.

        Returns:
            Combined defensive multiplier (0.0, 0.25, 0.5, 1.0, 2.0, or 4.0).
        """
        # Normalize defending_types to a tuple of unique PokemonType
        if isinstance(defending_types, (PokemonType, str)):
            raw_defenders: Sequence[PokemonType | str] = [defending_types]
        else:
            raw_defenders = defending_types

        if not raw_defenders:
            raise InvalidTypeMatchupError("At least one defending type must be provided.")

        normalized_defenders = [_normalize_type(d) for d in raw_defenders]
        # Preserve order while deduplicating
        unique_defenders = tuple(dict.fromkeys(normalized_defenders))

        if len(unique_defenders) > 2:
            raise InvalidTypeMatchupError(
                f"A Pokemon can have at most two defending types, got {len(unique_defenders)}."
            )

        multiplier = 1.0
        for defender in unique_defenders:
            single_mult = self.calculate_single_matchup(
                attacking_type, defender, chart_context
            )
            multiplier *= single_mult
            # Short-circuit on immunity
            if multiplier == 0.0:
                return 0.0

        return multiplier

    def get_matchup_result(
        self,
        attacking_type: PokemonType | str,
        defending_types: PokemonType | str | Sequence[PokemonType | str],
        chart_context: TypeChartVersion | GameRuleProfile | str,
    ) -> TypeMatchupResult:
        """Calculate matchup and return a structured TypeMatchupResult."""
        atk = _normalize_type(attacking_type)
        chart_version = _resolve_chart_version(chart_context)

        if isinstance(defending_types, (PokemonType, str)):
            defenders = (defending_types,)
        else:
            defenders = tuple(defending_types)

        norm_defenders = tuple(dict.fromkeys(_normalize_type(d) for d in defenders))
        mult = self.calculate_matchup(atk, norm_defenders, chart_version)

        return TypeMatchupResult(
            attacking_type=atk,
            defending_types=norm_defenders,
            multiplier=mult,
            chart_version=chart_version,
        )


# Global default instance
matchup_engine = TypeMatchupEngine()
