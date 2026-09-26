"""Central SQLAlchemy model import module for Alembic migration discovery."""

from app.db.session import Base
from app.models.orm import (
    Ability,
    BaseStat,
    ElementType,
    Game,
    GamePokemon,
    GameRuleProfileModel,
    Generation,
    Pokemon,
    PokemonAbilityAssignment,
    PokemonTypeAssignment,
    TypeChartEntry,
)

__all__ = [
    "Ability",
    "Base",
    "BaseStat",
    "ElementType",
    "Game",
    "GamePokemon",
    "GameRuleProfileModel",
    "Generation",
    "Pokemon",
    "PokemonAbilityAssignment",
    "PokemonTypeAssignment",
    "TypeChartEntry",
]
