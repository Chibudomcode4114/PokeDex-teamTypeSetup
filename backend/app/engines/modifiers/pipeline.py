"""Defensive modifier execution pipeline.

Chains pluggable defensive modifiers after pure type effectiveness calculations,
preserving both base and final multipliers.
"""

from collections.abc import Sequence

from app.engines.modifiers.ability_modifiers import (
    FlashFireModifier,
    LevitateModifier,
    ThickFatModifier,
    VoltAbsorbModifier,
    WaterAbsorbModifier,
)
from app.engines.modifiers.base import DefensiveModifier, ModifierContext
from app.models.domain import (
    GameRuleProfile,
    ModifiedMatchupResult,
    TypeMatchupResult,
)

# Canonical MVP modifier set
MVP_DEFAULT_MODIFIERS: tuple[DefensiveModifier, ...] = (
    LevitateModifier(),
    FlashFireModifier(),
    WaterAbsorbModifier(),
    VoltAbsorbModifier(),
    ThickFatModifier(),
)


class DefensiveModifierPipeline:
    """Evaluates a chain of defensive modifiers against a calculated base matchup."""

    def __init__(self, modifiers: Sequence[DefensiveModifier] | None = None) -> None:
        if modifiers is None:
            self._modifiers: list[DefensiveModifier] = list(MVP_DEFAULT_MODIFIERS)
        else:
            self._modifiers = list(modifiers)

    def apply(
        self,
        base_result: TypeMatchupResult,
        rule_profile: GameRuleProfile,
        ability: str | None = None,
    ) -> ModifiedMatchupResult:
        """Apply active defensive modifiers to a base TypeMatchupResult.

        Args:
            base_result: Pure type matchup result from TypeMatchupEngine.
            rule_profile: Resolved GameRuleProfile defining game mechanics.
            ability: Name of the defending Pokémon's ability (optional).

        Returns:
            A new ModifiedMatchupResult containing both base and final multipliers.
            The input base_result is never mutated.
        """
        current_multiplier = base_result.multiplier
        applied_names: list[str] = []

        for modifier in self._modifiers:
            context = ModifierContext(
                attacking_type=base_result.attacking_type,
                defending_types=base_result.defending_types,
                base_multiplier=base_result.multiplier,
                current_multiplier=current_multiplier,
                ability=ability,
                rule_profile=rule_profile,
            )
            if modifier.applies(context):
                current_multiplier = modifier.apply(context)
                applied_names.append(modifier.name)

        return ModifiedMatchupResult(
            attacking_type=base_result.attacking_type,
            defending_types=base_result.defending_types,
            base_multiplier=base_result.multiplier,
            final_multiplier=current_multiplier,
            applied_modifiers=tuple(applied_names),
            ability=ability,
            chart_version=base_result.chart_version,
        )


# Global default pipeline instance
modifier_pipeline = DefensiveModifierPipeline()
