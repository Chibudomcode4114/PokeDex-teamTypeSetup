"""Integration tests for FastAPI Pokémon Catalog & Game Context API endpoints (Milestone 3B).

Tests HTTP presentation layer via TestClient against internal SQLite database.
Validates routing, Pydantic serialization, status codes, query aliases, and cross-game divergence.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.adapters.pokeapi.normalizer import PokeApiNormalizer
from app.adapters.pokeapi.schemas import (
    NormalizedAbilityAssignment,
    NormalizedBaseStats,
    NormalizedPokemon,
    NormalizedTypeAssignment,
)
from app.db.session import get_db
from app.main import app
from app.services.ingestion_service import IngestionService

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    """Load JSON fixture from local test fixtures."""
    path = FIXTURES_DIR / f"{name}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def seeded_api_db(db_session: Session) -> Session:
    """Seed test database with canonical game contexts and offline test Pokémon."""
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


@pytest.fixture
def api_client(seeded_api_db: Session) -> Generator[TestClient]:
    """Provide a TestClient with database dependency overridden to seeded session."""

    def override_get_db() -> Generator[Session]:
        yield seeded_api_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ==============================================================================
# 1. Games Endpoint Tests (GET /api/v1/games)
# ==============================================================================


class TestGamesApi:
    """Test suite for GET /api/v1/games and GET /api/v1/games/{game_id}/rules."""

    def test_get_games_success(self, api_client: TestClient) -> None:
        """Verify GET /api/v1/games returns supported MVP games in deterministic order."""
        response = api_client.get("/api/v1/games")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 4

        game_ids = [g["id"] for g in data]
        assert game_ids == ["firered", "leafgreen", "pokemon-x", "pokemon-y"]

        # Verify field structure and types
        first = data[0]
        assert first["id"] == "firered"
        assert first["title"] == "Pokémon FireRed"
        assert first["generation_id"] == "gen-3"
        assert first["generation_number"] == 3
        assert first["version_group"] == "firered-leafgreen"
        assert first["is_supported"] is True

    def test_get_game_rules_firered(self, api_client: TestClient) -> None:
        """Verify GET /api/v1/games/{game_id}/rules for FireRed (Gen III)."""
        response = api_client.get("/api/v1/games/firered/rules")
        assert response.status_code == 200

        data = response.json()
        assert data["game_id"] == "firered"
        assert data["generation"] == 3
        assert data["type_chart_version"] == "gen2_5"
        assert data["physical_special_model"] == "by_type"

        flags = data["mechanic_flags"]
        assert flags["has_fairy_type"] is False
        assert flags["steel_resists_dark_ghost"] is True
        assert flags["physical_special_split"] is False
        assert flags["has_abilities"] is True

        assert "fairy" not in data["supported_types"]
        assert len(data["supported_types"]) == 17

    def test_get_game_rules_pokemon_x(self, api_client: TestClient) -> None:
        """Verify GET /api/v1/games/{game_id}/rules for Pokémon X (Gen VI)."""
        response = api_client.get("/api/v1/games/pokemon-x/rules")
        assert response.status_code == 200

        data = response.json()
        assert data["game_id"] == "pokemon_x"
        assert data["generation"] == 6
        assert data["type_chart_version"] == "gen6_plus"

        flags = data["mechanic_flags"]
        assert flags["has_fairy_type"] is True
        assert flags["steel_resists_dark_ghost"] is False
        assert flags["physical_special_split"] is True

        assert "fairy" in data["supported_types"]
        assert len(data["supported_types"]) == 18

    def test_get_game_rules_alias_resolution(self, api_client: TestClient) -> None:
        """Verify GET /api/v1/games/{game_id}/rules resolves common aliases (e.g. 'x')."""
        response = api_client.get("/api/v1/games/x/rules")
        assert response.status_code == 200
        assert response.json()["game_id"] == "pokemon_x"

    def test_get_game_rules_unsupported_game_returns_400(self, api_client: TestClient) -> None:
        """Verify GET /api/v1/games/{game_id}/rules returns HTTP 400 for unsupported games."""
        response = api_client.get("/api/v1/games/pokemon-emerald/rules")
        assert response.status_code == 400
        data = response.json()
        assert "not supported" in data["detail"].lower()


# ==============================================================================
# 2. Pokémon Search Endpoint Tests (GET /api/v1/pokemon)
# ==============================================================================


class TestPokemonSearchApi:
    """Test suite for GET /api/v1/pokemon."""

    def test_search_missing_game_id_returns_422(self, api_client: TestClient) -> None:
        """Verify omitting game_id returns HTTP 422 Unprocessable Entity."""
        response = api_client.get("/api/v1/pokemon")
        assert response.status_code == 422

    def test_search_unknown_game_returns_400(self, api_client: TestClient) -> None:
        """Verify unknown or unsupported game returns HTTP 400."""
        response = api_client.get("/api/v1/pokemon?game_id=unsupported-title")
        assert response.status_code == 400
        assert "not supported" in response.json()["detail"].lower()

    def test_search_firered_all(self, api_client: TestClient) -> None:
        """Verify default search returns all available FireRed Pokémon ordered deterministically."""
        response = api_client.get("/api/v1/pokemon?game_id=firered")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 4
        assert [p["id"] for p in data] == [
            "pidgeot",
            "clefairy",
            "gengar",
            "deoxys-attack",
        ]
        # Verify National Dex ordering
        assert [p["dex_number"] for p in data] == [18, 35, 94, 386]

        # Verify summary fields
        clefairy = data[1]
        assert clefairy["id"] == "clefairy"
        assert clefairy["name"] == "Clefairy"
        assert clefairy["species_name"] == "clefairy"
        assert clefairy["types"] == ["normal"]
        assert clefairy["is_available"] is True

    def test_search_canonical_query_parameter(self, api_client: TestClient) -> None:
        """Verify partial name matching with canonical 'search' parameter."""
        response = api_client.get("/api/v1/pokemon?game_id=firered&search=geng")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "gengar"

    def test_search_alias_q_parameter(self, api_client: TestClient) -> None:
        """Verify partial name matching works when using 'q' alias."""
        response = api_client.get("/api/v1/pokemon?game_id=firered&q=pidg")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "pidgeot"

    def test_search_conflicting_query_aliases_returns_422(self, api_client: TestClient) -> None:
        """Verify supplying conflicting 'search' and 'q' parameters raises HTTP 422."""
        response = api_client.get("/api/v1/pokemon?game_id=firered&search=gengar&q=clefairy")
        assert response.status_code == 422
        assert "ambiguous" in response.json()["detail"].lower()

    def test_search_matching_query_aliases_succeeds(self, api_client: TestClient) -> None:
        """Verify supplying identical 'search' and 'q' parameters succeeds."""
        response = api_client.get("/api/v1/pokemon?game_id=firered&search=gengar&q=gengar")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "gengar"

    def test_search_valid_type_filter(self, api_client: TestClient) -> None:
        """Verify filtering by valid elemental type."""
        response = api_client.get("/api/v1/pokemon?game_id=firered&type_filter=ghost")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "gengar"

    def test_search_unsupported_type_filter_returns_400(self, api_client: TestClient) -> None:
        """Verify filtering by Fairy in FireRed raises HTTP 400 (UnsupportedTypeError)."""
        response = api_client.get("/api/v1/pokemon?game_id=firered&type_filter=fairy")
        assert response.status_code == 400
        assert "fairy" in response.json()["detail"].lower()

    def test_search_type_filter_clefairy_fairy_in_pokemon_x(self, api_client: TestClient) -> None:
        """Verify filtering by Fairy in Pokémon X succeeds and returns Clefairy."""
        response = api_client.get("/api/v1/pokemon?game_id=pokemon-x&type_filter=fairy")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "clefairy"

    def test_search_pagination_limit_and_offset(self, api_client: TestClient) -> None:
        """Verify limit and offset pagination."""
        resp1 = api_client.get("/api/v1/pokemon?game_id=firered&limit=2&offset=0")
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert len(data1) == 2
        assert [p["id"] for p in data1] == ["pidgeot", "clefairy"]

        resp2 = api_client.get("/api/v1/pokemon?game_id=firered&limit=2&offset=2")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert len(data2) == 2
        assert [p["id"] for p in data2] == ["gengar", "deoxys-attack"]

    def test_search_invalid_pagination_returns_422(self, api_client: TestClient) -> None:
        """Verify limit < 1, limit > 100, or offset < 0 return HTTP 422."""
        resp_limit_zero = api_client.get("/api/v1/pokemon?game_id=firered&limit=0")
        assert resp_limit_zero.status_code == 422

        resp_limit_high = api_client.get("/api/v1/pokemon?game_id=firered&limit=101")
        assert resp_limit_high.status_code == 422

        resp_offset_neg = api_client.get("/api/v1/pokemon?game_id=firered&offset=-1")
        assert resp_offset_neg.status_code == 422


# ==============================================================================
# 3. Pokémon Detail Endpoint Tests (GET /api/v1/pokemon/{pokemon_id})
# ==============================================================================


class TestPokemonDetailApi:
    """Test suite for GET /api/v1/pokemon/{pokemon_id}."""

    def test_detail_missing_game_id_returns_422(self, api_client: TestClient) -> None:
        """Verify omitting game_id returns HTTP 422."""
        response = api_client.get("/api/v1/pokemon/clefairy")
        assert response.status_code == 422

    def test_detail_unknown_game_returns_400(self, api_client: TestClient) -> None:
        """Verify unknown game returns HTTP 400."""
        response = api_client.get("/api/v1/pokemon/clefairy?game_id=unknown-game")
        assert response.status_code == 400

    def test_detail_unknown_pokemon_returns_404(self, api_client: TestClient) -> None:
        """Verify unknown Pokémon ID returns HTTP 404."""
        response = api_client.get("/api/v1/pokemon/agumon?game_id=firered")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_detail_unavailable_pokemon_returns_404(self, api_client: TestClient) -> None:
        """Verify Pokémon exists in catalog but unavailable in game returns HTTP 404."""
        response = api_client.get("/api/v1/pokemon/unown?game_id=firered")
        assert response.status_code == 404
        assert "not available in game" in response.json()["detail"].lower()

    def test_detail_cross_game_clefairy_typing(self, api_client: TestClient) -> None:
        """Verify Clefairy is Normal in FireRed and Fairy in Pokémon X."""
        resp_fr = api_client.get("/api/v1/pokemon/clefairy?game_id=firered")
        assert resp_fr.status_code == 200
        fr_data = resp_fr.json()
        assert len(fr_data["types"]) == 1
        assert fr_data["types"][0]["type_id"] == "normal"
        assert fr_data["types"][0]["slot"] == 1

        resp_x = api_client.get("/api/v1/pokemon/clefairy?game_id=pokemon-x")
        assert resp_x.status_code == 200
        x_data = resp_x.json()
        assert len(x_data["types"]) == 1
        assert x_data["types"][0]["type_id"] == "fairy"
        assert x_data["types"][0]["slot"] == 1

    def test_detail_cross_game_pidgeot_stats_and_defense_serialization(
        self, api_client: TestClient
    ) -> None:
        """Verify Pidgeot Speed divergence (91 vs 101) and 'def' key serialization."""
        resp_fr = api_client.get("/api/v1/pokemon/pidgeot?game_id=firered")
        assert resp_fr.status_code == 200
        fr_data = resp_fr.json()
        assert fr_data["base_stats"]["spe"] == 91
        # Explicitly verify 'def' key is present in serialized JSON
        assert "def" in fr_data["base_stats"]
        assert fr_data["base_stats"]["def"] == 75

        resp_x = api_client.get("/api/v1/pokemon/pidgeot?game_id=pokemon-x")
        assert resp_x.status_code == 200
        x_data = resp_x.json()
        assert x_data["base_stats"]["spe"] == 101
        assert x_data["base_stats"]["def"] == 75

    def test_detail_deoxys_attack_identity_and_form(self, api_client: TestClient) -> None:
        """Verify Deoxys Attack preserves form_name, species_name, and national dex number."""
        response = api_client.get("/api/v1/pokemon/deoxys-attack?game_id=firered")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "deoxys-attack"
        assert data["dex_number"] == 386
        assert data["species_name"] == "deoxys"
        assert data["form_name"] == "attack"
        assert data["name"] == "Deoxys (Attack)"
