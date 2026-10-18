"""Pydantic schemas for Pokémon catalog and game context presentation contracts (Milestone 3B)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GameResponse(BaseModel):
    """Supported Pokémon game summary response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    generation_id: str
    generation_number: int
    version_group: str
    is_supported: bool


class MechanicFlagsResponse(BaseModel):
    """Game-specific battle and mechanic feature flags response."""

    model_config = ConfigDict(from_attributes=True)

    has_fairy_type: bool
    steel_resists_dark_ghost: bool
    physical_special_split: bool
    has_abilities: bool


class GameRuleProfileResponse(BaseModel):
    """Authoritative game rule profile response."""

    model_config = ConfigDict(from_attributes=True)

    game_id: str
    game_title: str
    generation: int
    type_chart_version: str
    physical_special_model: str
    supported_types: list[str]
    mechanic_flags: MechanicFlagsResponse


class PokemonSummaryResponse(BaseModel):
    """Game-filtered Pokémon catalog summary response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    dex_number: int
    name: str
    species_name: str
    form_name: str | None = None
    game_id: str
    types: list[str]
    is_available: bool


class PokemonTypeInfoResponse(BaseModel):
    """Game-specific Pokémon elemental type slot assignment."""

    model_config = ConfigDict(from_attributes=True)

    slot: int
    type_id: str
    name: str


class PokemonAbilityInfoResponse(BaseModel):
    """Game-specific Pokémon ability response."""

    model_config = ConfigDict(from_attributes=True)

    ability_id: str
    name: str
    is_hidden: bool


class PokemonBaseStatsResponse(BaseModel):
    """Game-specific base battle stats response."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    hp: int
    atk: int
    def_: int = Field(alias="def")
    spa: int
    spd: int
    spe: int


class PokemonDetailResponse(BaseModel):
    """Detailed game-specific Pokémon data model response."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    dex_number: int
    name: str
    species_name: str
    form_name: str | None = None
    game_id: str
    is_available: bool
    types: list[PokemonTypeInfoResponse]
    abilities: list[PokemonAbilityInfoResponse]
    base_stats: PokemonBaseStatsResponse
