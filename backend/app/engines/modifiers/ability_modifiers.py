"""Defensive ability modifier implementations.

Implements approved MVP defensive abilities:
- Levitate: Ground attacks -> 0.0
- Flash Fire: Fire attacks -> 0.0
- Water Absorb: Water attacks -> 0.0
- Volt Absorb: Electric attacks -> 0.0
- Thick Fat: Fire and Ice attacks -> current_multiplier * 0.5
"""

from app.engines.modifiers.base import ModifierContext
from app.models.domain import PokemonType


def _normalize_ability(ability: str | None) -> str | None:
    """Normalize ability string for whitespace, casing, hyphens, and underscores."""
    if not ability:
        return None
    return ability.strip().lower().replace("-", " ").replace("_", " ")


class LevitateModifier:
    """Levitate grants immunity to Ground-type attacks."""

    @property
    def name(self) -> str:
        return "Levitate"

    def applies(self, context: ModifierContext) -> bool:
        if not context.rule_profile.mechanic_flags.has_abilities:
            return False
        if _normalize_ability(context.ability) != "levitate":
            return False
        return context.attacking_type == PokemonType.GROUND

    def apply(self, context: ModifierContext) -> float:
        if not self.applies(context):
            return context.current_multiplier
        return 0.0


class FlashFireModifier:
    """Flash Fire grants immunity to Fire-type attacks."""

    @property
    def name(self) -> str:
        return "Flash Fire"

    def applies(self, context: ModifierContext) -> bool:
        if not context.rule_profile.mechanic_flags.has_abilities:
            return False
        if _normalize_ability(context.ability) != "flash fire":
            return False
        return context.attacking_type == PokemonType.FIRE

    def apply(self, context: ModifierContext) -> float:
        if not self.applies(context):
            return context.current_multiplier
        return 0.0


class WaterAbsorbModifier:
    """Water Absorb grants immunity to Water-type attacks."""

    @property
    def name(self) -> str:
        return "Water Absorb"

    def applies(self, context: ModifierContext) -> bool:
        if not context.rule_profile.mechanic_flags.has_abilities:
            return False
        if _normalize_ability(context.ability) != "water absorb":
            return False
        return context.attacking_type == PokemonType.WATER

    def apply(self, context: ModifierContext) -> float:
        if not self.applies(context):
            return context.current_multiplier
        return 0.0


class VoltAbsorbModifier:
    """Volt Absorb grants immunity to Electric-type attacks."""

    @property
    def name(self) -> str:
        return "Volt Absorb"

    def applies(self, context: ModifierContext) -> bool:
        if not context.rule_profile.mechanic_flags.has_abilities:
            return False
        if _normalize_ability(context.ability) != "volt absorb":
            return False
        return context.attacking_type == PokemonType.ELECTRIC

    def apply(self, context: ModifierContext) -> float:
        if not self.applies(context):
            return context.current_multiplier
        return 0.0


class ThickFatModifier:
    """Thick Fat halves damage from Fire-type and Ice-type attacks."""

    @property
    def name(self) -> str:
        return "Thick Fat"

    def applies(self, context: ModifierContext) -> bool:
        if not context.rule_profile.mechanic_flags.has_abilities:
            return False
        if _normalize_ability(context.ability) != "thick fat":
            return False
        return context.attacking_type in (PokemonType.FIRE, PokemonType.ICE)

    def apply(self, context: ModifierContext) -> float:
        if not self.applies(context):
            return context.current_multiplier
        return context.current_multiplier * 0.5
