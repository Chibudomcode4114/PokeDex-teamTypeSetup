"""Game endpoints (/api/v1/games) (Milestone 3B).

Provides game discovery and authoritative game rule profiles.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.catalog import GameResponse, GameRuleProfileResponse
from app.services.game_service import GameCatalogService

router = APIRouter()


@router.get("", response_model=list[GameResponse])
def get_games(session: Session = Depends(get_db)) -> list[GameResponse]:
    """Retrieve all supported games ordered by generation and title."""
    games = GameCatalogService.get_games(session)
    return [GameResponse.model_validate(g) for g in games]


@router.get("/{game_id}/rules", response_model=GameRuleProfileResponse)
def get_game_rules(game_id: str) -> GameRuleProfileResponse:
    """Retrieve the authoritative runtime rule profile for a specific game."""
    profile = GameCatalogService.get_game_rule_profile(game_id)
    return GameRuleProfileResponse.model_validate(profile)
