"""Service for persisting normalized PokeAPI catalog data into the relational database.

Translates NormalizedPokemon structures into SQLAlchemy ORM entities with idempotent
reconciliation, transaction atomicity, and reference data resolution.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.pokeapi.schemas import NormalizedPokemon
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
)

logger = logging.getLogger(__name__)


class IngestionService:
    """Service managing deterministic ingestion and reconciliation of normalized catalog data."""

    @classmethod
    def seed_game_contexts(cls, session: Session) -> None:
        """Seed canonical generations, games, and game rule profiles for the MVP.

        Operation is idempotent and safe to run on an existing database.
        """
        with session.begin_nested():
            # 1. Seed Generations
            generations_data = [
                {"id": "gen-3", "number": 3, "name": "Generation III"},
                {"id": "gen-6", "number": 6, "name": "Generation VI"},
            ]
            for gen_info in generations_data:
                existing_gen = session.get(Generation, gen_info["id"])
                if existing_gen is None:
                    session.add(
                        Generation(
                            id=gen_info["id"],
                            number=gen_info["number"],
                            name=gen_info["name"],
                        )
                    )

            session.flush()

            # 2. Seed Games and Rule Profiles
            games_data = [
                {
                    "id": "firered",
                    "title": "Pokémon FireRed",
                    "generation_id": "gen-3",
                    "version_group": "firered-leafgreen",
                    "is_supported": True,
                    "profile": {
                        "type_chart_version": "gen2_5",
                        "has_fairy_type": False,
                        "steel_resists_dark_ghost": True,
                    },
                },
                {
                    "id": "leafgreen",
                    "title": "Pokémon LeafGreen",
                    "generation_id": "gen-3",
                    "version_group": "firered-leafgreen",
                    "is_supported": True,
                    "profile": {
                        "type_chart_version": "gen2_5",
                        "has_fairy_type": False,
                        "steel_resists_dark_ghost": True,
                    },
                },
                {
                    "id": "pokemon-x",
                    "title": "Pokémon X",
                    "generation_id": "gen-6",
                    "version_group": "x-y",
                    "is_supported": True,
                    "profile": {
                        "type_chart_version": "gen6_plus",
                        "has_fairy_type": True,
                        "steel_resists_dark_ghost": False,
                    },
                },
                {
                    "id": "pokemon-y",
                    "title": "Pokémon Y",
                    "generation_id": "gen-6",
                    "version_group": "x-y",
                    "is_supported": True,
                    "profile": {
                        "type_chart_version": "gen6_plus",
                        "has_fairy_type": True,
                        "steel_resists_dark_ghost": False,
                    },
                },
            ]

            for g_info in games_data:
                game = session.get(Game, g_info["id"])
                if game is None:
                    game = Game(
                        id=g_info["id"],
                        title=g_info["title"],
                        generation_id=g_info["generation_id"],
                        version_group=g_info["version_group"],
                        is_supported=g_info["is_supported"],
                    )
                    session.add(game)
                    session.flush()

                # Ensure 1-to-1 GameRuleProfile
                profile_data = g_info["profile"]
                profile = session.get(GameRuleProfileModel, g_info["id"])
                if profile is None:
                    session.add(
                        GameRuleProfileModel(
                            game_id=g_info["id"],
                            type_chart_version=profile_data["type_chart_version"],
                            has_fairy_type=profile_data["has_fairy_type"],
                            steel_resists_dark_ghost=profile_data["steel_resists_dark_ghost"],
                        )
                    )

            session.flush()

    @classmethod
    def ensure_element_type(
        cls,
        session: Session,
        type_id: str,
        name: str | None = None,
    ) -> ElementType:
        """Resolve or persist an ElementType reference entity."""
        normalized_id = type_id.strip().lower()
        existing = session.get(ElementType, normalized_id)
        if existing is not None:
            return existing

        display_name = name or normalized_id.title()
        element_type = ElementType(id=normalized_id, name=display_name)
        session.add(element_type)
        session.flush()
        return element_type

    @classmethod
    def ensure_ability(
        cls,
        session: Session,
        ability_id: str,
        name: str | None = None,
    ) -> Ability:
        """Resolve or persist an Ability reference entity."""
        normalized_id = ability_id.strip().lower()
        existing = session.get(Ability, normalized_id)
        if existing is not None:
            return existing

        display_name = name or normalized_id.replace("-", " ").title()
        ability = Ability(id=normalized_id, name=display_name)
        session.add(ability)
        session.flush()
        return ability

    @classmethod
    def ingest_pokemon(
        cls,
        session: Session,
        normalized: NormalizedPokemon,
    ) -> Pokemon:
        """Atomically persist or reconcile a NormalizedPokemon for its game context.

        Guarantees:
        - Atomic execution inside a savepoint (sub-transaction).
        - Idempotent re-ingestion with stale state convergence.
        - Respects foreign keys and unique constraints.
        - Does not create duplicate reference types or abilities.
        """
        with session.begin_nested():
            # 1. Verify Target Game Exists
            target_game = session.get(Game, normalized.game_id)
            if target_game is None:
                raise ValueError(
                    f"Target game '{normalized.game_id}' does not exist in the database. "
                    "Ensure game contexts are seeded before ingesting Pokémon."
                )

            # 2. Persist / Update Core Pokemon Entity
            pokemon = session.get(Pokemon, normalized.id)
            if pokemon is None:
                pokemon = Pokemon(
                    id=normalized.id,
                    dex_number=normalized.dex_number,
                    name=normalized.name,
                    species_name=normalized.species_name,
                    form_name=normalized.form_name,
                )
                session.add(pokemon)
            else:
                pokemon.dex_number = normalized.dex_number
                pokemon.name = normalized.name
                pokemon.species_name = normalized.species_name
                pokemon.form_name = normalized.form_name

            session.flush()

            # 3. Persist / Update GamePokemon Availability
            game_poke_stmt = select(GamePokemon).where(
                GamePokemon.pokemon_id == normalized.id,
                GamePokemon.game_id == normalized.game_id,
            )
            game_poke = session.execute(game_poke_stmt).scalar_one_or_none()
            if game_poke is None:
                game_poke = GamePokemon(
                    game_id=normalized.game_id,
                    pokemon_id=normalized.id,
                    is_available=normalized.is_available,
                )
                session.add(game_poke)
            else:
                game_poke.is_available = normalized.is_available

            session.flush()

            # 4. Reconcile PokemonTypeAssignment Records
            # Ensure referenced ElementType records exist
            for type_assign in normalized.types:
                cls.ensure_element_type(session, type_assign.type_id)

            existing_types_stmt = select(PokemonTypeAssignment).where(
                PokemonTypeAssignment.pokemon_id == normalized.id,
                PokemonTypeAssignment.game_id == normalized.game_id,
            )
            existing_types = list(session.execute(existing_types_stmt).scalars().all())
            existing_types_by_slot = {t.slot: t for t in existing_types}

            target_slots = {t.slot for t in normalized.types}
            # Remove stale slots
            for slot, existing_assign in list(existing_types_by_slot.items()):
                if slot not in target_slots:
                    session.delete(existing_assign)

            # Update or insert current slots
            for type_assign in normalized.types:
                if type_assign.slot in existing_types_by_slot:
                    existing_types_by_slot[type_assign.slot].type_id = type_assign.type_id
                else:
                    session.add(
                        PokemonTypeAssignment(
                            pokemon_id=normalized.id,
                            game_id=normalized.game_id,
                            type_id=type_assign.type_id,
                            slot=type_assign.slot,
                        )
                    )

            session.flush()

            # 5. Reconcile PokemonAbilityAssignment Records
            # Ensure referenced Ability records exist
            for ability_assign in normalized.abilities:
                cls.ensure_ability(session, ability_assign.ability_id)

            existing_abilities_stmt = select(PokemonAbilityAssignment).where(
                PokemonAbilityAssignment.pokemon_id == normalized.id,
                PokemonAbilityAssignment.game_id == normalized.game_id,
            )
            existing_abilities = list(session.execute(existing_abilities_stmt).scalars().all())
            existing_abilities_by_id = {a.ability_id: a for a in existing_abilities}

            target_ability_ids = {a.ability_id for a in normalized.abilities}
            # Remove stale abilities
            for ab_id, existing_assign in list(existing_abilities_by_id.items()):
                if ab_id not in target_ability_ids:
                    session.delete(existing_assign)

            # Update or insert current abilities
            for ability_assign in normalized.abilities:
                if ability_assign.ability_id in existing_abilities_by_id:
                    existing_abilities_by_id[
                        ability_assign.ability_id
                    ].is_hidden = ability_assign.is_hidden
                else:
                    session.add(
                        PokemonAbilityAssignment(
                            pokemon_id=normalized.id,
                            game_id=normalized.game_id,
                            ability_id=ability_assign.ability_id,
                            is_hidden=ability_assign.is_hidden,
                        )
                    )

            session.flush()

            # 6. Reconcile BaseStat Records
            base_stat_stmt = select(BaseStat).where(
                BaseStat.pokemon_id == normalized.id,
                BaseStat.game_id == normalized.game_id,
            )
            base_stat = session.execute(base_stat_stmt).scalar_one_or_none()
            if base_stat is None:
                base_stat = BaseStat(
                    pokemon_id=normalized.id,
                    game_id=normalized.game_id,
                    hp=normalized.base_stats.hp,
                    atk=normalized.base_stats.atk,
                    def_=normalized.base_stats.def_,
                    spa=normalized.base_stats.spa,
                    spd=normalized.base_stats.spd,
                    spe=normalized.base_stats.spe,
                )
                session.add(base_stat)
            else:
                base_stat.hp = normalized.base_stats.hp
                base_stat.atk = normalized.base_stats.atk
                base_stat.def_ = normalized.base_stats.def_
                base_stat.spa = normalized.base_stats.spa
                base_stat.spd = normalized.base_stats.spd
                base_stat.spe = normalized.base_stats.spe

            session.flush()

        return pokemon

    @classmethod
    def ingest_pokemon_batch(
        cls,
        session: Session,
        items: Sequence[NormalizedPokemon],
    ) -> list[Pokemon]:
        """Ingest a sequence of NormalizedPokemon records."""
        return [cls.ingest_pokemon(session, item) for item in items]
