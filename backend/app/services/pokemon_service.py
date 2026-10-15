"""Pokémon Catalog Service: game-filtered queries, search, and details (Milestone 3A).

Provides deterministic querying of normalized Pokémon data scoped by explicit game context.
Enforces game context boundaries, prevents N+1 queries, and exposes domain dataclasses.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import (
    InvalidPaginationError,
    PokemonNotFoundError,
    PokemonUnavailableInGameError,
    UnsupportedTypeError,
)
from app.models.orm import (
    BaseStat,
    GamePokemon,
    Pokemon,
    PokemonAbilityAssignment,
    PokemonTypeAssignment,
)
from app.services.game_service import GameCatalogService


@dataclass(frozen=True)
class PokemonSummary:
    """Application-facing summary of a Pokémon in a specific game context."""

    id: str
    dex_number: int
    name: str
    species_name: str
    form_name: str | None
    game_id: str
    types: tuple[str, ...]
    is_available: bool


@dataclass(frozen=True)
class PokemonTypeInfo:
    """Game-specific elemental type assignment info."""

    slot: int
    type_id: str
    name: str


@dataclass(frozen=True)
class PokemonAbilityInfo:
    """Game-specific ability info.

    Note: Persisted PokemonAbilityAssignment schema does not store slot numbering.
    Abilities are returned in deterministic order: standard abilities first (is_hidden=False),
    then hidden abilities (is_hidden=True), ordered by ability_id.
    """

    ability_id: str
    name: str
    is_hidden: bool


@dataclass(frozen=True)
class PokemonBaseStatsInfo:
    """Game-specific base battle stats."""

    hp: int
    atk: int
    def_: int
    spa: int
    spd: int
    spe: int


@dataclass(frozen=True)
class PokemonDetail:
    """Detailed game-specific Pokémon data model."""

    id: str
    dex_number: int
    name: str
    species_name: str
    form_name: str | None
    game_id: str
    is_available: bool
    types: tuple[PokemonTypeInfo, ...]
    abilities: tuple[PokemonAbilityInfo, ...]
    base_stats: PokemonBaseStatsInfo


class PokemonCatalogService:
    """Service providing search and detail queries for Pokémon in explicit game contexts."""

    DEFAULT_LIMIT = 50
    MAX_LIMIT = 100

    @classmethod
    def validate_pagination(cls, limit: int, offset: int) -> tuple[int, int]:
        """Validate pagination parameters.

        Raises:
            InvalidPaginationError: If limit or offset values are out of bounds.
        """
        if not isinstance(limit, int) or limit < 1 or limit > cls.MAX_LIMIT:
            raise InvalidPaginationError(
                f"limit must be an integer between 1 and {cls.MAX_LIMIT}, got {limit}"
            )
        if not isinstance(offset, int) or offset < 0:
            raise InvalidPaginationError(f"offset must be a non-negative integer, got {offset}")
        return limit, offset

    @classmethod
    def search_pokemon(
        cls,
        session: Session,
        game_id: str,
        query: str | None = None,
        type_filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PokemonSummary]:
        """Search Pokémon available in the specified game context.

        Args:
            session: Active SQLAlchemy database session.
            game_id: Explicit required game identifier.
            query: Optional case-insensitive partial match for name or identifier.
            type_filter: Optional type identifier to filter by (using the game's typing).
            limit: Maximum items to return (1-100).
            offset: Zero-based pagination offset.

        Returns:
            List of PokemonSummary dataclasses ordered by dex_number ASC, id ASC.

        Raises:
            GameNotFoundError: If game_id is unknown or unsupported.
            InvalidPaginationError: If limit or offset are invalid.
        """
        # 1. Enforce explicit game context
        game = GameCatalogService.get_game(session, game_id)
        canonical_game_id = game.id

        # 2. Validate pagination
        valid_limit, valid_offset = cls.validate_pagination(limit, offset)

        # 3. Base Query: Only Pokémon available in this game
        stmt = (
            select(Pokemon)
            .join(
                GamePokemon,
                (GamePokemon.pokemon_id == Pokemon.id) & (GamePokemon.game_id == canonical_game_id),
            )
            .where(GamePokemon.is_available.is_(True))
        )

        # 4. Partial query search on name or slug/id
        if query and query.strip():
            cleaned_query = query.strip().lower()
            stmt = stmt.where(
                func.lower(Pokemon.name).contains(cleaned_query)
                | func.lower(Pokemon.id).contains(cleaned_query)
            )

        # 5. Type filtering strictly using the target game's supported types and type assignments
        if type_filter is not None:
            cleaned_type = type_filter.strip().lower()
            rule_profile = GameCatalogService.get_game_rule_profile(canonical_game_id)
            if not cleaned_type or not rule_profile.is_type_supported(cleaned_type):
                raise UnsupportedTypeError(
                    f"Type '{type_filter.strip()}' is not supported in '{game.title}'."
                )

            stmt = stmt.where(
                Pokemon.id.in_(
                    select(PokemonTypeAssignment.pokemon_id).where(
                        PokemonTypeAssignment.game_id == canonical_game_id,
                        PokemonTypeAssignment.type_id == cleaned_type,
                    )
                )
            )

        # 6. Deterministic ordering and pagination
        stmt = (
            stmt.order_by(Pokemon.dex_number.asc(), Pokemon.id.asc())
            .offset(valid_offset)
            .limit(valid_limit)
        )
        pokemon_list = list(session.execute(stmt).scalars().all())

        if not pokemon_list:
            return []

        # 7. Batch-load types for all matched Pokémon in this game to avoid N+1 queries
        poke_ids = [p.id for p in pokemon_list]
        types_stmt = (
            select(PokemonTypeAssignment)
            .where(
                PokemonTypeAssignment.game_id == canonical_game_id,
                PokemonTypeAssignment.pokemon_id.in_(poke_ids),
            )
            .order_by(PokemonTypeAssignment.slot.asc())
        )
        type_assignments = session.execute(types_stmt).scalars().all()

        types_by_pokemon: dict[str, list[str]] = defaultdict(list)
        for ta in type_assignments:
            types_by_pokemon[ta.pokemon_id].append(ta.type_id)

        # 8. Transform to application summary contracts
        return [
            PokemonSummary(
                id=p.id,
                dex_number=p.dex_number,
                name=p.name,
                species_name=p.species_name,
                form_name=p.form_name,
                game_id=canonical_game_id,
                types=tuple(types_by_pokemon.get(p.id, [])),
                is_available=True,
            )
            for p in pokemon_list
        ]

    @classmethod
    def get_pokemon_details(
        cls,
        session: Session,
        game_id: str,
        pokemon_id: str,
    ) -> PokemonDetail:
        """Retrieve full game-specific Pokémon details.

        Args:
            session: Active SQLAlchemy database session.
            game_id: Explicit required game identifier.
            pokemon_id: Unique Pokémon identifier.

        Returns:
            PokemonDetail containing game-accurate types, abilities, and base stats.

        Raises:
            GameNotFoundError: If game_id is unknown or unsupported.
            PokemonNotFoundError: If pokemon_id does not exist in the catalog.
            PokemonUnavailableInGameError: If the Pokémon is not available in the specified game.
        """
        # 1. Enforce explicit game context
        game = GameCatalogService.get_game(session, game_id)
        canonical_game_id = game.id

        if not pokemon_id or not isinstance(pokemon_id, str):
            raise PokemonNotFoundError(str(pokemon_id))

        normalized_pokemon_id = pokemon_id.strip().lower()

        # 2. Check if Pokémon exists in catalog
        pokemon = session.get(Pokemon, normalized_pokemon_id)
        if pokemon is None:
            raise PokemonNotFoundError(pokemon_id)

        # 3. Check availability in target game
        avail_stmt = select(GamePokemon).where(
            GamePokemon.game_id == canonical_game_id,
            GamePokemon.pokemon_id == normalized_pokemon_id,
        )
        game_poke = session.execute(avail_stmt).scalar_one_or_none()
        if game_poke is None or not game_poke.is_available:
            raise PokemonUnavailableInGameError(pokemon_id, game_id)

        # 4. Query game-specific types
        types_stmt = (
            select(PokemonTypeAssignment)
            .options(joinedload(PokemonTypeAssignment.type))
            .where(
                PokemonTypeAssignment.game_id == canonical_game_id,
                PokemonTypeAssignment.pokemon_id == normalized_pokemon_id,
            )
            .order_by(PokemonTypeAssignment.slot.asc())
        )
        type_records = session.execute(types_stmt).scalars().all()
        types = tuple(
            PokemonTypeInfo(
                slot=tr.slot,
                type_id=tr.type_id,
                name=tr.type.name if tr.type else tr.type_id.title(),
            )
            for tr in type_records
        )

        # 5. Query game-specific abilities
        # Note: Schema limitation: ability slot is not stored; deterministic order is applied.
        abilities_stmt = (
            select(PokemonAbilityAssignment)
            .options(joinedload(PokemonAbilityAssignment.ability))
            .where(
                PokemonAbilityAssignment.game_id == canonical_game_id,
                PokemonAbilityAssignment.pokemon_id == normalized_pokemon_id,
            )
            .order_by(
                PokemonAbilityAssignment.is_hidden.asc(),
                PokemonAbilityAssignment.ability_id.asc(),
            )
        )
        ability_records = session.execute(abilities_stmt).scalars().all()
        abilities = tuple(
            PokemonAbilityInfo(
                ability_id=ar.ability_id,
                name=ar.ability.name if ar.ability else ar.ability_id.replace("-", " ").title(),
                is_hidden=ar.is_hidden,
            )
            for ar in ability_records
        )

        # 6. Query game-specific base stats
        stats_stmt = select(BaseStat).where(
            BaseStat.game_id == canonical_game_id,
            BaseStat.pokemon_id == normalized_pokemon_id,
        )
        stats_record = session.execute(stats_stmt).scalar_one_or_none()
        if stats_record is not None:
            base_stats = PokemonBaseStatsInfo(
                hp=stats_record.hp,
                atk=stats_record.atk,
                def_=stats_record.def_,
                spa=stats_record.spa,
                spd=stats_record.spd,
                spe=stats_record.spe,
            )
        else:
            base_stats = PokemonBaseStatsInfo(hp=0, atk=0, def_=0, spa=0, spd=0, spe=0)

        return PokemonDetail(
            id=pokemon.id,
            dex_number=pokemon.dex_number,
            name=pokemon.name,
            species_name=pokemon.species_name,
            form_name=pokemon.form_name,
            game_id=canonical_game_id,
            is_available=game_poke.is_available,
            types=types,
            abilities=abilities,
            base_stats=base_stats,
        )
