"""Game Service: registry, lookup, and metadata for supported games (Milestone 3A).

This service interfaces with the relational database to query supported game contexts
and delegates to GameRulesEngine for authoritative runtime rule profiles.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import GameNotFoundError
from app.engines.rules_engine import rules_engine
from app.models.domain import GameRuleProfile
from app.models.orm import Game

# Known aliases mapping common variations to canonical database game IDs
GAME_ID_ALIASES: dict[str, str] = {
    "pokemon-firered": "firered",
    "pokemon_firered": "firered",
    "pokemon-leafgreen": "leafgreen",
    "pokemon_leafgreen": "leafgreen",
    "pokemon_x": "pokemon-x",
    "x": "pokemon-x",
    "pokemon_y": "pokemon-y",
    "y": "pokemon-y",
}


@dataclass(frozen=True)
class GameSummary:
    """Application-facing summary of a supported Pokémon game."""

    id: str
    title: str
    generation_id: str
    generation_number: int
    version_group: str
    is_supported: bool


class GameCatalogService:
    """Service providing query operations for game catalog contexts."""

    @classmethod
    def resolve_canonical_game_id(cls, game_id: str) -> str:
        """Resolve a game ID or alias to its canonical database identifier."""
        normalized = game_id.strip().lower()
        return GAME_ID_ALIASES.get(normalized, normalized)

    @classmethod
    def get_games(cls, session: Session) -> list[GameSummary]:
        """Retrieve all supported MVP games ordered deterministically.

        Ordered by Generation number ascending, then Game ID ascending.
        """
        stmt = (
            select(Game)
            .options(joinedload(Game.generation))
            .where(Game.is_supported.is_(True))
            .order_by(Game.generation_id.asc(), Game.id.asc())
        )
        games = session.execute(stmt).scalars().unique().all()
        # Sort by generation number then id to guarantee deterministic generational order
        sorted_games = sorted(
            games,
            key=lambda g: (g.generation.number if g.generation else 0, g.id),
        )

        return [
            GameSummary(
                id=g.id,
                title=g.title,
                generation_id=g.generation_id,
                generation_number=g.generation.number if g.generation else 0,
                version_group=g.version_group,
                is_supported=g.is_supported,
            )
            for g in sorted_games
        ]

    @classmethod
    def get_game(cls, session: Session, game_id: str) -> GameSummary:
        """Retrieve a single supported game by ID or alias.

        Raises:
            GameNotFoundError: If the game does not exist or is not supported.
        """
        if not game_id or not isinstance(game_id, str):
            raise GameNotFoundError(str(game_id))

        canonical_id = cls.resolve_canonical_game_id(game_id)
        stmt = (
            select(Game)
            .options(joinedload(Game.generation))
            .where(Game.id == canonical_id, Game.is_supported.is_(True))
        )
        game = session.execute(stmt).scalar_one_or_none()

        if game is None:
            raise GameNotFoundError(game_id)

        return GameSummary(
            id=game.id,
            title=game.title,
            generation_id=game.generation_id,
            generation_number=game.generation.number if game.generation else 0,
            version_group=game.version_group,
            is_supported=game.is_supported,
        )

    @classmethod
    def get_game_rule_profile(cls, game_id: str) -> GameRuleProfile:
        """Retrieve the authoritative runtime rule profile for a game.

        Delegates directly to GameRulesEngine.
        """
        if not game_id or not isinstance(game_id, str):
            raise GameNotFoundError(str(game_id))
        return rules_engine.resolve(game_id)
