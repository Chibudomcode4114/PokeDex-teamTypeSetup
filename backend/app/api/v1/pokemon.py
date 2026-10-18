"""Pokémon catalog endpoints (/api/v1/pokemon) (Milestone 3B).

Provides game-scoped search, type-filtering, and detailed Pokémon data retrieval.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.catalog import PokemonDetailResponse, PokemonSummaryResponse
from app.services.pokemon_service import PokemonCatalogService

router = APIRouter()


@router.get("", response_model=list[PokemonSummaryResponse])
def search_pokemon(
    game_id: str = Query(..., description="Target game context identifier (required)"),
    search: str | None = Query(default=None, description="Canonical search query parameter"),
    q: str | None = Query(default=None, description="Optional search query alias"),
    type_filter: str | None = Query(default=None, description="Elemental type filter"),
    limit: int = Query(default=50, description="Maximum items to return (1-100)"),
    offset: int = Query(default=0, description="Zero-based pagination offset"),
    session: Session = Depends(get_db),
) -> list[PokemonSummaryResponse]:
    """Search Pokémon available in the specified game context."""
    # Resolve ambiguous query aliases
    if search is not None and q is not None and search.strip() != q.strip():
        raise HTTPException(
            status_code=422,
            detail="Ambiguous query: provide either 'search' or 'q', not conflicting values.",
        )

    resolved_query = search if search is not None else q

    results = PokemonCatalogService.search_pokemon(
        session=session,
        game_id=game_id,
        query=resolved_query,
        type_filter=type_filter,
        limit=limit,
        offset=offset,
    )
    return [PokemonSummaryResponse.model_validate(p) for p in results]


@router.get("/{pokemon_id}", response_model=PokemonDetailResponse)
def get_pokemon_details(
    pokemon_id: str,
    game_id: str = Query(..., description="Target game context identifier (required)"),
    session: Session = Depends(get_db),
) -> PokemonDetailResponse:
    """Retrieve full game-accurate details for a Pokémon."""
    detail = PokemonCatalogService.get_pokemon_details(
        session=session,
        game_id=game_id,
        pokemon_id=pokemon_id,
    )
    return PokemonDetailResponse.model_validate(detail)
