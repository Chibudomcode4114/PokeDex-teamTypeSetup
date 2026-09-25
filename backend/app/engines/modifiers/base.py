"""Defensive modifier base protocol and context abstraction.

Provides a pluggable contract for non-type defensive modifications (e.g. abilities,
items, weather) evaluated downstream of the pure TypeMatchupEngine.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.models.domain import GameRuleProfile, PokemonType


@dataclass(frozen=True)
class ModifierContext:
    """Pure domain context provided to defensive modifiers during evaluation."""

    attacking_type: PokemonType
    defending_types: tuple[PokemonType, ...]
    base_multiplier: float
    current_multiplier: float
    ability: str | None
    rule_profile: GameRuleProfile


@runtime_checkable
class DefensiveModifier(Protocol):
    """Protocol defining a defensive modifier plugin."""

    @property
    def name(self) -> str:
        """Display name of the modifier (e.g. 'Levitate')."""
        ...

    def applies(self, context: ModifierContext) -> bool:
        """Evaluate whether this modifier is active and applies to the given context.

        Args:
            context: The evaluation context.

        Returns:
            True if the modifier should be applied, False otherwise.
        """
        ...

    def apply(self, context: ModifierContext) -> float:
        """Calculate and return the adjusted defensive multiplier.

        Args:
            context: The evaluation context containing the current multiplier.

        Returns:
            The adjusted multiplier. If the modifier does not apply, it must return
            context.current_multiplier unchanged.
        """
        ...
