"""Integration tests for PokeAPI IngestionService.

Verifies deterministic persistence and reconciliation of normalized PokeAPI catalog data
into SQLAlchemy ORM entities. Executes completely offline using local JSON fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.pokeapi.normalizer import PokeApiNormalizer
from app.adapters.pokeapi.schemas import (
    NormalizedAbilityAssignment,
    NormalizedBaseStats,
    NormalizedPokemon,
    NormalizedTypeAssignment,
    TargetGameContext,
)
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
from app.services.ingestion_service import IngestionService

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(fixture_name: str) -> dict[str, Any]:
    """Load a JSON fixture from the local fixtures directory."""
    path = FIXTURES_DIR / f"{fixture_name}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestPokeApiIngestion:
    """Test suite verifying persistence, reconciliation, and game isolation."""

    def test_seed_game_contexts_idempotent(self, db_session: Session) -> None:
        """Verify seeding canonical MVP games, generations, and rule profiles is idempotent."""
        # First seeding run
        IngestionService.seed_game_contexts(db_session)

        # Verify Generations
        gen3 = db_session.get(Generation, "gen-3")
        assert gen3 is not None
        assert gen3.number == 3
        assert gen3.name == "Generation III"

        gen6 = db_session.get(Generation, "gen-6")
        assert gen6 is not None
        assert gen6.number == 6
        assert gen6.name == "Generation VI"

        # Verify Games
        games = db_session.execute(select(Game)).scalars().all()
        assert len(games) == 4
        game_ids = {g.id for g in games}
        assert game_ids == {"firered", "leafgreen", "pokemon-x", "pokemon-y"}

        # Verify Rule Profiles
        firered_profile = db_session.get(GameRuleProfileModel, "firered")
        assert firered_profile is not None
        assert firered_profile.type_chart_version == "gen2_5"
        assert firered_profile.has_fairy_type is False
        assert firered_profile.steel_resists_dark_ghost is True

        xy_profile = db_session.get(GameRuleProfileModel, "pokemon-x")
        assert xy_profile is not None
        assert xy_profile.type_chart_version == "gen6_plus"
        assert xy_profile.has_fairy_type is True
        assert xy_profile.steel_resists_dark_ghost is False

        # Second seeding run (idempotency check)
        IngestionService.seed_game_contexts(db_session)
        assert len(db_session.execute(select(Generation)).scalars().all()) == 2
        assert len(db_session.execute(select(Game)).scalars().all()) == 4
        assert len(db_session.execute(select(GameRuleProfileModel)).scalars().all()) == 4

    def test_ensure_reference_data_resolution(self, db_session: Session) -> None:
        """Verify ElementType and Ability records are created and reused without duplication."""
        # Types
        type1 = IngestionService.ensure_element_type(db_session, "fire")
        type2 = IngestionService.ensure_element_type(db_session, "FIRE ")
        assert type1.id == "fire"
        assert type1.id == type2.id
        all_types = db_session.execute(select(ElementType)).scalars().all()
        assert len(all_types) == 1

        # Abilities
        ab1 = IngestionService.ensure_ability(db_session, "speed-boost")
        ab2 = IngestionService.ensure_ability(db_session, " speed-boost ")
        assert ab1.id == "speed-boost"
        assert ab1.id == ab2.id
        all_abilities = db_session.execute(select(Ability)).scalars().all()
        assert len(all_abilities) == 1

    def test_basic_pokemon_ingestion(self, db_session: Session) -> None:
        """Verify full ingestion of a normalized Pokémon into relational tables."""
        IngestionService.seed_game_contexts(db_session)

        fixture = load_fixture("pokeapi_clefairy")
        normalized = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=fixture["pokemon"],
            species_payload=fixture["species"],
            target_game="firered",
        )

        persisted = IngestionService.ingest_pokemon(db_session, normalized)
        assert persisted.id == "clefairy"

        # Check Pokemon table
        poke = db_session.get(Pokemon, "clefairy")
        assert poke is not None
        assert poke.dex_number == 35
        assert poke.name == "Clefairy"
        assert poke.species_name == "clefairy"
        assert poke.form_name is None

        # Check GamePokemon table
        gp = db_session.execute(
            select(GamePokemon).where(
                GamePokemon.pokemon_id == "clefairy",
                GamePokemon.game_id == "firered",
            )
        ).scalar_one_or_none()
        assert gp is not None
        assert gp.is_available is True

        # Check PokemonTypeAssignment table
        types = (
            db_session.execute(
                select(PokemonTypeAssignment).where(
                    PokemonTypeAssignment.pokemon_id == "clefairy",
                    PokemonTypeAssignment.game_id == "firered",
                )
            )
            .scalars()
            .all()
        )
        assert len(types) == 1
        assert types[0].slot == 1
        assert types[0].type_id == "normal"

        # Check PokemonAbilityAssignment table
        abilities = (
            db_session.execute(
                select(PokemonAbilityAssignment).where(
                    PokemonAbilityAssignment.pokemon_id == "clefairy",
                    PokemonAbilityAssignment.game_id == "firered",
                )
            )
            .scalars()
            .all()
        )
        assert len(abilities) == 1
        assert abilities[0].ability_id == "cute-charm"
        assert abilities[0].is_hidden is False

        # Check BaseStat table
        stats = db_session.execute(
            select(BaseStat).where(
                BaseStat.pokemon_id == "clefairy",
                BaseStat.game_id == "firered",
            )
        ).scalar_one_or_none()
        assert stats is not None
        assert stats.hp == 70
        assert stats.atk == 45
        assert stats.def_ == 48
        assert stats.spa == 60
        assert stats.spd == 65
        assert stats.spe == 35

    def test_cross_game_clefairy_typing(self, db_session: Session) -> None:
        """Verify Clefairy persists as Normal in FireRed and Fairy in Pokémon X simultaneously."""
        IngestionService.seed_game_contexts(db_session)
        fixture = load_fixture("pokeapi_clefairy")

        # Ingest for FireRed (Gen III)
        norm_fr = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=fixture["pokemon"],
            species_payload=fixture["species"],
            target_game="firered",
        )
        IngestionService.ingest_pokemon(db_session, norm_fr)

        # Ingest for Pokémon X (Gen VI)
        norm_x = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=fixture["pokemon"],
            species_payload=fixture["species"],
            target_game="pokemon-x",
        )
        IngestionService.ingest_pokemon(db_session, norm_x)

        # Proof query for FireRed
        fr_types = (
            db_session.execute(
                select(PokemonTypeAssignment)
                .where(
                    PokemonTypeAssignment.pokemon_id == "clefairy",
                    PokemonTypeAssignment.game_id == "firered",
                )
                .order_by(PokemonTypeAssignment.slot)
            )
            .scalars()
            .all()
        )
        assert len(fr_types) == 1
        assert fr_types[0].slot == 1
        assert fr_types[0].type_id == "normal"

        # Proof query for Pokémon X
        x_types = (
            db_session.execute(
                select(PokemonTypeAssignment)
                .where(
                    PokemonTypeAssignment.pokemon_id == "clefairy",
                    PokemonTypeAssignment.game_id == "pokemon-x",
                )
                .order_by(PokemonTypeAssignment.slot)
            )
            .scalars()
            .all()
        )
        assert len(x_types) == 1
        assert x_types[0].slot == 1
        assert x_types[0].type_id == "fairy"

    def test_cross_game_pidgeot_stats(self, db_session: Session) -> None:
        """Verify Pidgeot persists with Speed 91 in FireRed and Speed 101 in Pokémon X."""
        IngestionService.seed_game_contexts(db_session)
        fixture = load_fixture("pokeapi_pidgeot")

        norm_fr = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=fixture["pokemon"],
            species_payload=fixture["species"],
            target_game="firered",
        )
        IngestionService.ingest_pokemon(db_session, norm_fr)

        norm_x = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=fixture["pokemon"],
            species_payload=fixture["species"],
            target_game="pokemon-x",
        )
        IngestionService.ingest_pokemon(db_session, norm_x)

        # Proof query: FireRed base stats
        fr_stats = db_session.execute(
            select(BaseStat).where(
                BaseStat.pokemon_id == "pidgeot",
                BaseStat.game_id == "firered",
            )
        ).scalar_one()
        assert fr_stats.spe == 91

        # Proof query: Pokémon X base stats
        x_stats = db_session.execute(
            select(BaseStat).where(
                BaseStat.pokemon_id == "pidgeot",
                BaseStat.game_id == "pokemon-x",
            )
        ).scalar_one()
        assert x_stats.spe == 101

    def test_cross_game_gengar_abilities(self, db_session: Session) -> None:
        """Verify Gengar persists with Levitate in both FireRed and Pokémon X."""
        IngestionService.seed_game_contexts(db_session)
        fixture = load_fixture("pokeapi_gengar")

        norm_fr = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=fixture["pokemon"],
            species_payload=fixture["species"],
            target_game="firered",
        )
        IngestionService.ingest_pokemon(db_session, norm_fr)

        norm_x = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=fixture["pokemon"],
            species_payload=fixture["species"],
            target_game="pokemon-x",
        )
        IngestionService.ingest_pokemon(db_session, norm_x)

        # Proof query: FireRed abilities
        fr_abilities = (
            db_session.execute(
                select(PokemonAbilityAssignment).where(
                    PokemonAbilityAssignment.pokemon_id == "gengar",
                    PokemonAbilityAssignment.game_id == "firered",
                )
            )
            .scalars()
            .all()
        )
        assert len(fr_abilities) == 1
        assert fr_abilities[0].ability_id == "levitate"
        assert fr_abilities[0].is_hidden is False

        # Proof query: Pokémon X abilities
        x_abilities = (
            db_session.execute(
                select(PokemonAbilityAssignment).where(
                    PokemonAbilityAssignment.pokemon_id == "gengar",
                    PokemonAbilityAssignment.game_id == "pokemon-x",
                )
            )
            .scalars()
            .all()
        )
        assert len(x_abilities) == 1
        assert x_abilities[0].ability_id == "levitate"
        assert x_abilities[0].is_hidden is False

    def test_deoxys_attack_form_identity(self, db_session: Session) -> None:
        """Verify Deoxys Attack preserves National Dex 386 and distinct form identity."""
        IngestionService.seed_game_contexts(db_session)
        fixture = load_fixture("pokeapi_deoxys_attack")

        norm_fr = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=fixture["pokemon"],
            species_payload=fixture["species"],
            target_game="firered",
        )
        IngestionService.ingest_pokemon(db_session, norm_fr)

        poke = db_session.get(Pokemon, "deoxys-attack")
        assert poke is not None
        assert poke.id == "deoxys-attack"
        assert poke.dex_number == 386  # Crucial: NOT the PokeAPI internal ID 10001
        assert poke.name == "Deoxys (Attack)"
        assert poke.species_name == "deoxys"
        assert poke.form_name == "attack"

    def test_ingestion_idempotency(self, db_session: Session) -> None:
        """Verify repeated ingestion of identical data causes no duplication or integrity errors."""
        IngestionService.seed_game_contexts(db_session)
        fixture = load_fixture("pokeapi_clefairy")

        norm_fr = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=fixture["pokemon"],
            species_payload=fixture["species"],
            target_game="firered",
        )

        # Ingest twice
        IngestionService.ingest_pokemon(db_session, norm_fr)
        IngestionService.ingest_pokemon(db_session, norm_fr)

        # Row counts must remain exactly 1
        assert (
            len(db_session.execute(select(Pokemon).where(Pokemon.id == "clefairy")).scalars().all())
            == 1
        )
        assert (
            len(
                db_session.execute(
                    select(GamePokemon).where(
                        GamePokemon.pokemon_id == "clefairy",
                        GamePokemon.game_id == "firered",
                    )
                )
                .scalars()
                .all()
            )
            == 1
        )
        assert (
            len(
                db_session.execute(
                    select(PokemonTypeAssignment).where(
                        PokemonTypeAssignment.pokemon_id == "clefairy",
                        PokemonTypeAssignment.game_id == "firered",
                    )
                )
                .scalars()
                .all()
            )
            == 1
        )
        assert (
            len(
                db_session.execute(
                    select(BaseStat).where(
                        BaseStat.pokemon_id == "clefairy",
                        BaseStat.game_id == "firered",
                    )
                )
                .scalars()
                .all()
            )
            == 1
        )

    def test_reconciliation_cleans_stale_data(self, db_session: Session) -> None:
        """Verify re-ingestion cleans up stale slots and abilities when attributes change."""
        IngestionService.seed_game_contexts(db_session)

        # 1. Initial State: Dual type (fire / flying), 2 abilities (blaze, solar-power)
        initial_norm = NormalizedPokemon(
            id="charizard-test",
            dex_number=6,
            name="Charizard Test",
            species_name="charizard",
            form_name=None,
            is_default=True,
            slug="charizard-test",
            game_id="firered",
            types=(
                NormalizedTypeAssignment(slot=1, type_id="fire"),
                NormalizedTypeAssignment(slot=2, type_id="flying"),
            ),
            abilities=(
                NormalizedAbilityAssignment(slot=1, ability_id="blaze", is_hidden=False),
                NormalizedAbilityAssignment(slot=2, ability_id="solar-power", is_hidden=True),
            ),
            base_stats=NormalizedBaseStats(hp=78, atk=84, def_=78, spa=109, spd=85, spe=100),
            is_available=True,
        )
        IngestionService.ingest_pokemon(db_session, initial_norm)

        # Verify initial counts
        types = (
            db_session.execute(
                select(PokemonTypeAssignment).where(
                    PokemonTypeAssignment.pokemon_id == "charizard-test",
                    PokemonTypeAssignment.game_id == "firered",
                )
            )
            .scalars()
            .all()
        )
        assert len(types) == 2

        abilities = (
            db_session.execute(
                select(PokemonAbilityAssignment).where(
                    PokemonAbilityAssignment.pokemon_id == "charizard-test",
                    PokemonAbilityAssignment.game_id == "firered",
                )
            )
            .scalars()
            .all()
        )
        assert len(abilities) == 2

        # 2. Re-ingest with changed state: Single type (dragon only at slot 1, slot 2 removed),
        # 1 ability (tough-claws only, previous abilities removed), updated stats
        updated_norm = NormalizedPokemon(
            id="charizard-test",
            dex_number=6,
            name="Charizard Test",
            species_name="charizard",
            form_name=None,
            is_default=True,
            slug="charizard-test",
            game_id="firered",
            types=(NormalizedTypeAssignment(slot=1, type_id="dragon"),),
            abilities=(
                NormalizedAbilityAssignment(slot=1, ability_id="tough-claws", is_hidden=False),
            ),
            base_stats=NormalizedBaseStats(hp=78, atk=130, def_=111, spa=130, spd=85, spe=100),
            is_available=True,
        )
        IngestionService.ingest_pokemon(db_session, updated_norm)

        # Verify reconciliation
        types_after = (
            db_session.execute(
                select(PokemonTypeAssignment).where(
                    PokemonTypeAssignment.pokemon_id == "charizard-test",
                    PokemonTypeAssignment.game_id == "firered",
                )
            )
            .scalars()
            .all()
        )
        assert len(types_after) == 1
        assert types_after[0].slot == 1
        assert types_after[0].type_id == "dragon"

        abilities_after = (
            db_session.execute(
                select(PokemonAbilityAssignment).where(
                    PokemonAbilityAssignment.pokemon_id == "charizard-test",
                    PokemonAbilityAssignment.game_id == "firered",
                )
            )
            .scalars()
            .all()
        )
        assert len(abilities_after) == 1
        assert abilities_after[0].ability_id == "tough-claws"

        stats_after = db_session.execute(
            select(BaseStat).where(
                BaseStat.pokemon_id == "charizard-test",
                BaseStat.game_id == "firered",
            )
        ).scalar_one()
        assert stats_after.atk == 130
        assert stats_after.def_ == 111

    def test_game_isolation(self, db_session: Session) -> None:
        """Verify data ingested for one game context does not leak into another."""
        IngestionService.seed_game_contexts(db_session)
        fixture = load_fixture("pokeapi_clefairy")

        # Ingest only into FireRed
        norm_fr = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=fixture["pokemon"],
            species_payload=fixture["species"],
            target_game="firered",
        )
        IngestionService.ingest_pokemon(db_session, norm_fr)

        # Pokémon X must have no records for Clefairy
        x_gp = db_session.execute(
            select(GamePokemon).where(
                GamePokemon.pokemon_id == "clefairy",
                GamePokemon.game_id == "pokemon-x",
            )
        ).scalar_one_or_none()
        assert x_gp is None

        x_types = (
            db_session.execute(
                select(PokemonTypeAssignment).where(
                    PokemonTypeAssignment.pokemon_id == "clefairy",
                    PokemonTypeAssignment.game_id == "pokemon-x",
                )
            )
            .scalars()
            .all()
        )
        assert len(x_types) == 0

        x_stats = db_session.execute(
            select(BaseStat).where(
                BaseStat.pokemon_id == "clefairy",
                BaseStat.game_id == "pokemon-x",
            )
        ).scalar_one_or_none()
        assert x_stats is None

    def test_transaction_rollback_on_missing_game(self, db_session: Session) -> None:
        """Verify invalid target game raises ValueError and rolls back savepoint cleanly."""
        # Create a normalized model pointing to an unseeded / non-existent game
        norm = NormalizedPokemon(
            id="clefairy-fail",
            dex_number=35,
            name="Clefairy",
            species_name="clefairy",
            form_name=None,
            is_default=True,
            slug="clefairy-fail",
            game_id="non-existent-game",
            types=(NormalizedTypeAssignment(slot=1, type_id="normal"),),
            abilities=(
                NormalizedAbilityAssignment(slot=1, ability_id="cute-charm", is_hidden=False),
            ),
            base_stats=NormalizedBaseStats(hp=70, atk=45, def_=48, spa=60, spd=65, spe=35),
            is_available=True,
        )

        with pytest.raises(ValueError, match="does not exist in the database"):
            IngestionService.ingest_pokemon(db_session, norm)

        # Verify nothing was persisted
        poke = db_session.get(Pokemon, "clefairy-fail")
        assert poke is None

        # Verify session is still valid and not poisoned
        IngestionService.seed_game_contexts(db_session)
        assert db_session.get(Generation, "gen-3") is not None

    def test_shared_reference_data_deduplication(self, db_session: Session) -> None:
        """Verify multiple Pokémon sharing types/abilities do not duplicate reference rows."""
        IngestionService.seed_game_contexts(db_session)

        clef = load_fixture("pokeapi_clefairy")
        pidg = load_fixture("pokeapi_pidgeot")

        norm_clef = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=clef["pokemon"],
            species_payload=clef["species"],
            target_game="firered",
        )
        norm_pidg = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=pidg["pokemon"],
            species_payload=pidg["species"],
            target_game="firered",
        )

        # Both Clefairy and Pidgeot share "normal" type in FireRed
        IngestionService.ingest_pokemon(db_session, norm_clef)
        IngestionService.ingest_pokemon(db_session, norm_pidg)

        normal_types = (
            db_session.execute(select(ElementType).where(ElementType.id == "normal"))
            .scalars()
            .all()
        )
        assert len(normal_types) == 1

    def test_multi_boundary_historical_resolution(self, db_session: Session) -> None:
        """Verify multi-boundary historical resolution persists correctly across generations."""
        # Setup generations and games for Gen 3, 5, 7
        with db_session.begin_nested():
            for g_id, g_num in [("gen-3", 3), ("gen-5", 5), ("gen-7", 7)]:
                if not db_session.get(Generation, g_id):
                    db_session.add(Generation(id=g_id, number=g_num, name=f"Generation {g_num}"))
            for g_id, gen_fk, vg in [
                ("game-gen3", "gen-3", "ruby-sapphire"),
                ("game-gen5", "gen-5", "black-white"),
                ("game-gen7", "gen-7", "sun-moon"),
            ]:
                if not db_session.get(Game, g_id):
                    db_session.add(
                        Game(
                            id=g_id,
                            title=g_id,
                            generation_id=gen_fk,
                            version_group=vg,
                            is_supported=True,
                        )
                    )
            db_session.flush()

        synthetic_pokemon = {
            "id": 999,
            "name": "synthmon",
            "stats": [
                {"base_stat": 30, "stat": {"name": "speed"}},
                {"base_stat": 30, "stat": {"name": "hp"}},
                {"base_stat": 30, "stat": {"name": "attack"}},
                {"base_stat": 30, "stat": {"name": "defense"}},
                {"base_stat": 30, "stat": {"name": "special-attack"}},
                {"base_stat": 30, "stat": {"name": "special-defense"}},
            ],
            "types": [{"slot": 1, "type": {"name": "dragon"}}],
            "abilities": [{"slot": 1, "is_hidden": False, "ability": {"name": "cursed-body"}}],
            "past_types": [
                {
                    "generation": {"name": "generation-iv"},
                    "types": [{"slot": 1, "type": {"name": "fire"}}],
                },
                {
                    "generation": {"name": "generation-vi"},
                    "types": [{"slot": 1, "type": {"name": "water"}}],
                },
            ],
            "past_abilities": [
                {
                    "generation": {"name": "generation-iv"},
                    "abilities": [{"slot": 1, "is_hidden": False, "ability": {"name": "pressure"}}],
                },
                {
                    "generation": {"name": "generation-vi"},
                    "abilities": [{"slot": 1, "is_hidden": False, "ability": {"name": "levitate"}}],
                },
            ],
            "past_stats": [
                {
                    "generation": {"name": "generation-iv"},
                    "stats": [
                        {"base_stat": 10, "stat": {"name": "speed"}},
                        {"base_stat": 10, "stat": {"name": "hp"}},
                        {"base_stat": 10, "stat": {"name": "attack"}},
                        {"base_stat": 10, "stat": {"name": "defense"}},
                        {"base_stat": 10, "stat": {"name": "special-attack"}},
                        {"base_stat": 10, "stat": {"name": "special-defense"}},
                    ],
                },
                {
                    "generation": {"name": "generation-vi"},
                    "stats": [
                        {"base_stat": 20, "stat": {"name": "speed"}},
                        {"base_stat": 20, "stat": {"name": "hp"}},
                        {"base_stat": 20, "stat": {"name": "attack"}},
                        {"base_stat": 20, "stat": {"name": "defense"}},
                        {"base_stat": 20, "stat": {"name": "special-attack"}},
                        {"base_stat": 20, "stat": {"name": "special-defense"}},
                    ],
                },
            ],
        }
        synthetic_species = {
            "id": 999,
            "name": "synthmon",
            "generation": {"name": "generation-i"},
            "varieties": [{"is_default": True, "pokemon": {"name": "synthmon"}}],
        }

        # Normalize and ingest for Gen 3 (target generation 3 <= IV boundary -> Fire, 10, Pressure)
        norm_gen3 = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=synthetic_pokemon,
            species_payload=synthetic_species,
            target_game=TargetGameContext(
                game_id="game-gen3",
                generation=3,
                version_name="gen3",
                version_group="ruby-sapphire",
            ),
        )
        IngestionService.ingest_pokemon(db_session, norm_gen3)

        # Normalize and ingest for Gen 5 (target generation 5 <= VI boundary -> Water, 20, Levitate)
        norm_gen5 = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=synthetic_pokemon,
            species_payload=synthetic_species,
            target_game=TargetGameContext(
                game_id="game-gen5",
                generation=5,
                version_name="gen5",
                version_group="black-white",
            ),
        )
        IngestionService.ingest_pokemon(db_session, norm_gen5)

        # Normalize and ingest for Gen 7 (target gen 7 > VI boundary -> Dragon, 30, Cursed-body)
        norm_gen7 = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=synthetic_pokemon,
            species_payload=synthetic_species,
            target_game=TargetGameContext(
                game_id="game-gen7",
                generation=7,
                version_name="gen7",
                version_group="sun-moon",
            ),
        )
        IngestionService.ingest_pokemon(db_session, norm_gen7)

        # Verify Gen 3
        gen3_type = db_session.execute(
            select(PokemonTypeAssignment).where(
                PokemonTypeAssignment.pokemon_id == "synthmon",
                PokemonTypeAssignment.game_id == "game-gen3",
            )
        ).scalar_one()
        assert gen3_type.type_id == "fire"

        gen3_ab = db_session.execute(
            select(PokemonAbilityAssignment).where(
                PokemonAbilityAssignment.pokemon_id == "synthmon",
                PokemonAbilityAssignment.game_id == "game-gen3",
            )
        ).scalar_one()
        assert gen3_ab.ability_id == "pressure"

        gen3_stat = db_session.execute(
            select(BaseStat).where(
                BaseStat.pokemon_id == "synthmon",
                BaseStat.game_id == "game-gen3",
            )
        ).scalar_one()
        assert gen3_stat.spe == 10

        # Verify Gen 5
        gen5_type = db_session.execute(
            select(PokemonTypeAssignment).where(
                PokemonTypeAssignment.pokemon_id == "synthmon",
                PokemonTypeAssignment.game_id == "game-gen5",
            )
        ).scalar_one()
        assert gen5_type.type_id == "water"

        gen5_ab = db_session.execute(
            select(PokemonAbilityAssignment).where(
                PokemonAbilityAssignment.pokemon_id == "synthmon",
                PokemonAbilityAssignment.game_id == "game-gen5",
            )
        ).scalar_one()
        assert gen5_ab.ability_id == "levitate"

        gen5_stat = db_session.execute(
            select(BaseStat).where(
                BaseStat.pokemon_id == "synthmon",
                BaseStat.game_id == "game-gen5",
            )
        ).scalar_one()
        assert gen5_stat.spe == 20

        # Verify Gen 7
        gen7_type = db_session.execute(
            select(PokemonTypeAssignment).where(
                PokemonTypeAssignment.pokemon_id == "synthmon",
                PokemonTypeAssignment.game_id == "game-gen7",
            )
        ).scalar_one()
        assert gen7_type.type_id == "dragon"

        gen7_ab = db_session.execute(
            select(PokemonAbilityAssignment).where(
                PokemonAbilityAssignment.pokemon_id == "synthmon",
                PokemonAbilityAssignment.game_id == "game-gen7",
            )
        ).scalar_one()
        assert gen7_ab.ability_id == "cursed-body"

        gen7_stat = db_session.execute(
            select(BaseStat).where(
                BaseStat.pokemon_id == "synthmon",
                BaseStat.game_id == "game-gen7",
            )
        ).scalar_one()
        assert gen7_stat.spe == 30

    def test_batch_ingestion(self, db_session: Session) -> None:
        """Verify batch ingestion method processes all items."""
        IngestionService.seed_game_contexts(db_session)
        fixture_clef = load_fixture("pokeapi_clefairy")
        fixture_pidg = load_fixture("pokeapi_pidgeot")

        norm_clef = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=fixture_clef["pokemon"],
            species_payload=fixture_clef["species"],
            target_game="firered",
        )
        norm_pidg = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=fixture_pidg["pokemon"],
            species_payload=fixture_pidg["species"],
            target_game="firered",
        )

        persisted = IngestionService.ingest_pokemon_batch(db_session, [norm_clef, norm_pidg])
        assert len(persisted) == 2
        assert persisted[0].id == "clefairy"
        assert persisted[1].id == "pidgeot"
