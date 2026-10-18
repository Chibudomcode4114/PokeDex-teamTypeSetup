"""API v1 master router."""

from fastapi import APIRouter

from app.api.v1.games import router as games_router
from app.api.v1.pokemon import router as pokemon_router

api_router = APIRouter()

api_router.include_router(games_router, prefix="/games", tags=["Games"])
api_router.include_router(pokemon_router, prefix="/pokemon", tags=["Pokemon"])
