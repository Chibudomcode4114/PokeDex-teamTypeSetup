"""Integration tests for GameCatalogService and PokemonCatalogService (Milestone 3A).

Executes strictly against the internal normalized relational database using offline fixtures.
Verifies explicit game context enforcement, search, cross-game typing/stats/abilities,
deterministic ordering, N+1 query safety, and domain error differentiation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.adapters.pokeapi.normalizer import PokeApiNormalizer
from app.adapters.pokeapi.schemas import (
    NormalizedAbilityAssignment,
    NormalizedBaseStats,
    NormalizedPokemon,
    NormalizedTypeAssignment,
)
from app.core.errors import (
    GameNotFoundError,
    InvalidPaginationError,
    PokemonNotFoundError,
    PokemonUnavailableInGameError,
    UnsupportedTypeError,
)
from app.engines.rules_engine import rules_engine
from app.services.game_service import GameCatalogService
from app.services.ingestion_service import IngestionService
from app.services.pokemon_service import PokemonCatalogService

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    """Load JSON fixture from local test fixtures."""
    path = FIXTURES_DIR / f"{name}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def seeded_db(db_session: Session) -> Session:
    """Provide a database seeded with canonical game contexts and offline test Pokémon."""
    IngestionService.seed_game_contexts(db_session)

    clef_data = load_fixture("pokeapi_clefairy")
    pidg_data = load_fixture("pokeapi_pidgeot")
    geng_data = load_fixture("pokeapi_gengar")
    deox_data = load_fixture("pokeapi_deoxys_attack")

    # Ingest Clefairy into FireRed (Gen III, Normal) and Pokémon X (Gen VI, Fairy)
    norm_clef_fr = PokeApiNormalizer.normalize_pokemon(
        clef_data["pokemon"], clef_data["species"], "firered"
    )
    norm_clef_x = PokeApiNormalizer.normalize_pokemon(
        clef_data["pokemon"], clef_data["species"], "pokemon-x"
    )
    IngestionService.ingest_pokemon(db_session, norm_clef_fr)
    IngestionService.ingest_pokemon(db_session, norm_clef_x)

    # Ingest Pidgeot into FireRed (Spe: 91) and Pokémon X (Spe: 101)
    norm_pidg_fr = PokeApiNormalizer.normalize_pokemon(
        pidg_data["pokemon"], pidg_data["species"], "firered"
    )
    norm_pidg_x = PokeApiNormalizer.normalize_pokemon(
        pidg_data["pokemon"], pidg_data["species"], "pokemon-x"
    )
    IngestionService.ingest_pokemon(db_session, norm_pidg_fr)
    IngestionService.ingest_pokemon(db_session, norm_pidg_x)

    # Ingest Gengar into FireRed and Pokémon X (Levitate in both)
    norm_geng_fr = PokeApiNormalizer.normalize_pokemon(
        geng_data["pokemon"], geng_data["species"], "firered"
    )
    norm_geng_x = PokeApiNormalizer.normalize_pokemon(
        geng_data["pokemon"], geng_data["species"], "pokemon-x"
    )
    IngestionService.ingest_pokemon(db_session, norm_geng_fr)
    IngestionService.ingest_pokemon(db_session, norm_geng_x)

    # Ingest Deoxys Attack into FireRed only (Dex 386, Form attack)
    norm_deox_fr = PokeApiNormalizer.normalize_pokemon(
        deox_data["pokemon"], deox_data["species"], "firered"
    )
    IngestionService.ingest_pokemon(db_session, norm_deox_fr)

    # Ingest an unavailable Pokémon in FireRed for explicit availability testing
    unavail_norm = NormalizedPokemon(
        id="unown",
        dex_number=201,
        name="Unown",
        species_name="unown",
        form_name=None,
        is_default=True,
        slug="unown",
        game_id="firered",
        types=(NormalizedTypeAssignment(slot=1, type_id="psychic"),),
        abilities=(NormalizedAbilityAssignment(slot=1, ability_id="levitate", is_hidden=False),),
        base_stats=NormalizedBaseStats(hp=48, atk=72, def_=48, spa=72, spd=48, spe=48),
        is_available=False,
    )
    IngestionService.ingest_pokemon(db_session, unavail_norm)

    return db_session


# ==============================================================================
# 1. Game Catalog Service Tests
# ==============================================================================


class TestGameCatalogService:
    """Test suite verifying game context registry, lookup, and rules engine delegation."""

    def test_get_games_lists_supported_mvp_games(self, seeded_db: Session) -> None:
        """Verify get_games returns the four supported MVP titles."""
        games = GameCatalogService.get_games(seeded_db)
        game_ids = [g.id for g in games]
        assert game_ids == ["firered", "leafgreen", "pokemon-x", "pokemon-y"]
        assert all(g.is_supported is True for g in games)

    def test_get_games_deterministic_ordering(self, seeded_db: Session) -> None:
        """Verify games are ordered deterministically by generation number then game ID."""
        games = GameCatalogService.get_games(seeded_db)
        # Gen III before Gen VI
        assert games[0].generation_number == 3
        assert games[1].generation_number == 3
        assert games[2].generation_number == 6
        assert games[3].generation_number == 6
        # Alphabetical by id within generation
        assert games[0].id == "firered"
        assert games[1].id == "leafgreen"
        assert games[2].id == "pokemon-x"
        assert games[3].id == "pokemon-y"

    def test_get_game_valid_retrieval_and_alias(self, seeded_db: Session) -> None:
        """Verify retrieving a supported game by canonical ID and alias."""
        game_fr = GameCatalogService.get_game(seeded_db, "firered")
        assert game_fr.id == "firered"
        assert game_fr.title == "Pokémon FireRed"
        assert game_fr.generation_id == "gen-3"

        # Alias resolution e.g. "x" -> "pokemon-x"
        game_x = GameCatalogService.get_game(seeded_db, "x")
        assert game_x.id == "pokemon-x"
        assert game_x.title == "Pokémon X"

    def test_get_game_rejects_unknown_or_unsupported(self, seeded_db: Session) -> None:
        """Verify get_game raises GameNotFoundError for unsupported games."""
        with pytest.raises(GameNotFoundError):
            GameCatalogService.get_game(seeded_db, "pokemon-emerald")

        with pytest.raises(GameNotFoundError):
            GameCatalogService.get_game(seeded_db, "")

    def test_get_game_rule_profile_agrees_with_rules_engine(self) -> None:
        """Verify game rule profile matches pure GameRulesEngine authoritative profiles."""
        for game_id in ["firered", "leafgreen", "pokemon-x", "pokemon-y"]:
            service_profile = GameCatalogService.get_game_rule_profile(game_id)
            engine_profile = rules_engine.resolve(game_id)
            assert service_profile == engine_profile

        with pytest.raises(GameNotFoundError):
            GameCatalogService.get_game_rule_profile("ruby")


# ==============================================================================
# 2. Pokémon Catalog Service Search Tests
# ==============================================================================


class TestPokemonCatalogSearch:
    """Test suite verifying search, filtering, deterministic pagination, and game isolation."""

    def test_search_requires_explicit_game_context(self, seeded_db: Session) -> None:
        """Verify searching without a valid game fails closed."""
        with pytest.raises(GameNotFoundError):
            PokemonCatalogService.search_pokemon(seeded_db, game_id="invalid-game")

        with pytest.raises(GameNotFoundError):
            PokemonCatalogService.search_pokemon(seeded_db, game_id="")

    def test_search_case_insensitive_partial_name(self, seeded_db: Session) -> None:
        """Verify partial name matching is case-insensitive."""
        results_lower = PokemonCatalogService.search_pokemon(
            seeded_db, game_id="firered", query="clef"
        )
        results_upper = PokemonCatalogService.search_pokemon(
            seeded_db, game_id="firered", query="CLEF"
        )
        results_mixed = PokemonCatalogService.search_pokemon(
            seeded_db, game_id="firered", query="cLeFaIrY"
        )

        assert len(results_lower) == 1
        assert results_lower[0].id == "clefairy"
        assert results_lower == results_upper == results_mixed

    def test_search_by_identifier_or_slug(self, seeded_db: Session) -> None:
        """Verify searching by Pokémon ID/slug works."""
        results = PokemonCatalogService.search_pokemon(
            seeded_db, game_id="firered", query="deoxys-attack"
        )
        assert len(results) == 1
        assert results[0].id == "deoxys-attack"
        assert results[0].dex_number == 386

    def test_search_excludes_unavailable_pokemon(self, seeded_db: Session) -> None:
        """Verify is_available=False Pokémon are excluded from search results."""
        # Unown was ingested with is_available=False in FireRed
        results = PokemonCatalogService.search_pokemon(seeded_db, game_id="firered", query="unown")
        assert len(results) == 0

    def test_search_deterministic_ordering(self, seeded_db: Session) -> None:
        """Verify default search ordering is dex_number ASC, id ASC."""
        # In FireRed: Clefairy (35), Pidgeot (18), Gengar (94), Deoxys Attack (386)
        results = PokemonCatalogService.search_pokemon(seeded_db, game_id="firered")
        dex_numbers = [r.dex_number for r in results]
        assert dex_numbers == [18, 35, 94, 386]
        assert [r.id for r in results] == [
            "pidgeot",
            "clefairy",
            "gengar",
            "deoxys-attack",
        ]

    def test_search_pagination_limit_and_offset(self, seeded_db: Session) -> None:
        """Verify limit and offset pagination work properly."""
        # Page 1: limit 2, offset 0 -> Pidgeot (18), Clefairy (35)
        page1 = PokemonCatalogService.search_pokemon(
            seeded_db, game_id="firered", limit=2, offset=0
        )
        assert len(page1) == 2
        assert page1[0].id == "pidgeot"
        assert page1[1].id == "clefairy"

        # Page 2: limit 2, offset 2 -> Gengar (94), Deoxys Attack (386)
        page2 = PokemonCatalogService.search_pokemon(
            seeded_db, game_id="firered", limit=2, offset=2
        )
        assert len(page2) == 2
        assert page2[0].id == "gengar"
        assert page2[1].id == "deoxys-attack"

    def test_search_invalid_pagination_rejected(self, seeded_db: Session) -> None:
        """Verify invalid limit and offset raise InvalidPaginationError."""
        with pytest.raises(InvalidPaginationError):
            PokemonCatalogService.search_pokemon(seeded_db, game_id="firered", limit=0)

        with pytest.raises(InvalidPaginationError):
            PokemonCatalogService.search_pokemon(seeded_db, game_id="firered", limit=101)

        with pytest.raises(InvalidPaginationError):
            PokemonCatalogService.search_pokemon(seeded_db, game_id="firered", offset=-1)


# ==============================================================================
# 3. Cross-Game Search and Detail Verification
# ==============================================================================


class TestCrossGameCatalogBehavior:
    """Test suite verifying historical game divergence in search and detail lookups."""

    def test_clefairy_cross_game_type_filtering(self, seeded_db: Session) -> None:
        """Verify Clefairy appears as Normal in FireRed and Fairy in Pokémon X."""
        # In FireRed: Clefairy has Normal type
        fr_normal = PokemonCatalogService.search_pokemon(
            seeded_db, game_id="firered", type_filter="normal"
        )
        assert any(p.id == "clefairy" for p in fr_normal)

        # In FireRed: Fairy type is unsupported and must raise UnsupportedTypeError
        with pytest.raises(UnsupportedTypeError, match="Type 'fairy' is not supported"):
            PokemonCatalogService.search_pokemon(seeded_db, game_id="firered", type_filter="fairy")

        # In Pokémon X: Clefairy has Fairy type
        x_fairy = PokemonCatalogService.search_pokemon(
            seeded_db, game_id="pokemon-x", type_filter="fairy"
        )
        assert any(p.id == "clefairy" for p in x_fairy)

        # In Pokémon X: Clefairy does NOT have Normal type (returns Pidgeot)
        x_normal = PokemonCatalogService.search_pokemon(
            seeded_db, game_id="pokemon-x", type_filter="normal"
        )
        assert not any(p.id == "clefairy" for p in x_normal)
        assert any(p.id == "pidgeot" for p in x_normal)

    def test_type_filter_validation_and_unsupported_type_rejection(
        self, seeded_db: Session
    ) -> None:
        """Verify type filter validation rules across games."""
        # 1. Fairy is rejected in FireRed (Gen III)
        with pytest.raises(UnsupportedTypeError, match="not supported in 'Pokémon FireRed'"):
            PokemonCatalogService.search_pokemon(seeded_db, game_id="firered", type_filter="fairy")

        # 2. Fairy works normally in Pokémon X (Gen VI)
        results_x = PokemonCatalogService.search_pokemon(
            seeded_db, game_id="pokemon-x", type_filter="fairy"
        )
        assert len(results_x) == 1
        assert results_x[0].id == "clefairy"

        # 3. Normalization of casing and whitespace works
        results_spaced = PokemonCatalogService.search_pokemon(
            seeded_db, game_id="pokemon-x", type_filter="  FAIRY  "
        )
        assert len(results_spaced) == 1
        assert results_spaced[0].id == "clefairy"

        # 4. Unknown type names are explicitly rejected
        with pytest.raises(UnsupportedTypeError):
            PokemonCatalogService.search_pokemon(seeded_db, game_id="firered", type_filter="banana")

        with pytest.raises(UnsupportedTypeError):
            PokemonCatalogService.search_pokemon(seeded_db, game_id="firered", type_filter="")

        with pytest.raises(UnsupportedTypeError):
            PokemonCatalogService.search_pokemon(seeded_db, game_id="pokemon-x", type_filter="   ")

        # 5. A valid supported type with no matching Pokémon returns an empty list
        # "ice" is a supported Gen III type, but none of the seeded Pokémon are Ice-type
        results_ice = PokemonCatalogService.search_pokemon(
            seeded_db, game_id="firered", type_filter="ice"
        )
        assert results_ice == []

    def test_clefairy_details_divergence(self, seeded_db: Session) -> None:
        """Verify get_pokemon_details returns Normal for FireRed and Fairy for Pokémon X."""
        detail_fr = PokemonCatalogService.get_pokemon_details(
            seeded_db, game_id="firered", pokemon_id="clefairy"
        )
        assert detail_fr.id == "clefairy"
        assert detail_fr.game_id == "firered"
        assert len(detail_fr.types) == 1
        assert detail_fr.types[0].slot == 1
        assert detail_fr.types[0].type_id == "normal"

        detail_x = PokemonCatalogService.get_pokemon_details(
            seeded_db, game_id="pokemon-x", pokemon_id="clefairy"
        )
        assert detail_x.id == "clefairy"
        assert detail_x.game_id == "pokemon-x"
        assert len(detail_x.types) == 1
        assert detail_x.types[0].slot == 1
        assert detail_x.types[0].type_id == "fairy"

    def test_pidgeot_stats_divergence(self, seeded_db: Session) -> None:
        """Verify Pidgeot details return Speed 91 in FireRed and Speed 101 in Pokémon X."""
        detail_fr = PokemonCatalogService.get_pokemon_details(
            seeded_db, game_id="firered", pokemon_id="pidgeot"
        )
        assert detail_fr.base_stats.spe == 91

        detail_x = PokemonCatalogService.get_pokemon_details(
            seeded_db, game_id="pokemon-x", pokemon_id="pidgeot"
        )
        assert detail_x.base_stats.spe == 101

    def test_gengar_abilities_persisted(self, seeded_db: Session) -> None:
        """Verify Gengar abilities are persisted and retrieved deterministically."""
        detail_fr = PokemonCatalogService.get_pokemon_details(
            seeded_db, game_id="firered", pokemon_id="gengar"
        )
        assert len(detail_fr.abilities) >= 1
        assert detail_fr.abilities[0].ability_id == "levitate"
        assert detail_fr.abilities[0].is_hidden is False

        detail_x = PokemonCatalogService.get_pokemon_details(
            seeded_db, game_id="pokemon-x", pokemon_id="gengar"
        )
        assert len(detail_x.abilities) >= 1
        assert detail_x.abilities[0].ability_id == "levitate"
        assert detail_x.abilities[0].is_hidden is False

    def test_deoxys_attack_identity_preservation(self, seeded_db: Session) -> None:
        """Verify Deoxys Attack preserves National Dex 386 and distinct form identity."""
        detail = PokemonCatalogService.get_pokemon_details(
            seeded_db, game_id="firered", pokemon_id="deoxys-attack"
        )
        assert detail.id == "deoxys-attack"
        assert detail.dex_number == 386
        assert detail.species_name == "deoxys"
        assert detail.form_name == "attack"
        assert detail.name == "Deoxys (Attack)"


# ==============================================================================
# 4. Error Handling and Context Isolation Tests
# ==============================================================================


class TestCatalogErrorHandlingAndIsolation:
    """Test suite verifying domain error differentiation and zero cross-game data leak."""

    def test_unknown_pokemon_raises_pokemon_not_found(self, seeded_db: Session) -> None:
        """Verify querying non-existent Pokémon raises PokemonNotFoundError."""
        with pytest.raises(PokemonNotFoundError):
            PokemonCatalogService.get_pokemon_details(
                seeded_db, game_id="firered", pokemon_id="missingno"
            )

    def test_unavailable_pokemon_raises_pokemon_unavailable(self, seeded_db: Session) -> None:
        """Verify querying unavailable Pokémon raises PokemonUnavailableInGameError."""
        # Deoxys Attack was only ingested into FireRed, not Pokémon X
        with pytest.raises(PokemonUnavailableInGameError):
            PokemonCatalogService.get_pokemon_details(
                seeded_db, game_id="pokemon-x", pokemon_id="deoxys-attack"
            )

        # Unown is in FireRed with is_available=False
        with pytest.raises(PokemonUnavailableInGameError):
            PokemonCatalogService.get_pokemon_details(
                seeded_db, game_id="firered", pokemon_id="unown"
            )

    def test_game_isolation_prevents_data_leakage(self, seeded_db: Session) -> None:
        """Verify data from FireRed does not leak into Pokémon X search or detail queries."""
        # In Pokémon X: Deoxys Attack should not appear in search
        results_x = PokemonCatalogService.search_pokemon(
            seeded_db, game_id="pokemon-x", query="deoxys"
        )
        assert len(results_x) == 0

        # In FireRed: Deoxys Attack should appear in search
        results_fr = PokemonCatalogService.search_pokemon(
            seeded_db, game_id="firered", query="deoxys"
        )
        assert len(results_fr) == 1
        assert results_fr[0].id == "deoxys-attack"
