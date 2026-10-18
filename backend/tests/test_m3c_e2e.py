"""End-to-end integration tests verifying M0-M3 complete pipeline (Milestone 3C).

Executes against an isolated, file-based SQLite database initialized via Alembic.
Verifies migration execution, seeding, unseeded smoke tests, fixture ingestion,
cross-game data accuracy, and error handling contracts.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.adapters.pokeapi.normalizer import PokeApiNormalizer
from app.adapters.pokeapi.schemas import (
    NormalizedAbilityAssignment,
    NormalizedBaseStats,
    NormalizedPokemon,
    NormalizedTypeAssignment,
)
from app.db.session import get_db
from app.main import app
from app.services.game_service import GameCatalogService
from app.services.ingestion_service import IngestionService

BACKEND_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    """Load JSON fixture from local test fixtures."""
    path = FIXTURES_DIR / f"{name}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def disposable_e2e_db(tmp_path: Path) -> Generator[tuple[Session, sessionmaker[Session]]]:
    """Create a disposable file-based SQLite database initialized via Alembic migrations."""
    db_file = tmp_path / "m3c_disposable_test.db"
    db_url = f"sqlite:///{db_file}"

    alembic_ini_path = BACKEND_ROOT / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    alembic_cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))

    # Execute Alembic migration on fresh disposable database
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = factory()
    try:
        yield session, factory
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def disposable_client(
    disposable_e2e_db: tuple[Session, sessionmaker[Session]],
) -> Generator[TestClient]:
    """Provide a TestClient bound to the disposable migrated database."""
    _, factory = disposable_e2e_db

    def override_get_db() -> Generator[Session]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestMilestone3CEndToEnd:
    """Milestone 3C End-to-End verification test suite."""

    def test_database_initialization_and_game_seeding(
        self,
        disposable_e2e_db: tuple[Session, sessionmaker[Session]],
        disposable_client: TestClient,
    ) -> None:
        """Verify Alembic migration creates schema, seeding populates games,
        and unseeded catalog returns [].
        """
        session, _ = disposable_e2e_db

        # 1. Run canonical game seeding
        IngestionService.seed_game_contexts(session)
        session.commit()

        # 2. Verify all 4 MVP games exist
        games = GameCatalogService.get_games(session)
        assert [g.id for g in games] == ["firered", "leafgreen", "pokemon-x", "pokemon-y"]
        assert all(g.is_supported for g in games)

        # 3. Real application smoke tests (unseeded catalog)
        resp_health = disposable_client.get("/api/v1/health")
        assert resp_health.status_code == 200
        assert resp_health.json()["status"] == "ok"

        resp_games = disposable_client.get("/api/v1/games")
        assert resp_games.status_code == 200
        assert len(resp_games.json()) == 4

        resp_fr_rules = disposable_client.get("/api/v1/games/firered/rules")
        assert resp_fr_rules.status_code == 200
        assert resp_fr_rules.json()["mechanic_flags"]["has_fairy_type"] is False

        resp_x_rules = disposable_client.get("/api/v1/games/pokemon-x/rules")
        assert resp_x_rules.status_code == 200
        assert resp_x_rules.json()["mechanic_flags"]["has_fairy_type"] is True

        # Unseeded catalog search returns empty list rather than exception
        resp_empty_search = disposable_client.get("/api/v1/pokemon?game_id=firered")
        assert resp_empty_search.status_code == 200
        assert resp_empty_search.json() == []

    def test_complete_e2e_flow_with_ingested_fixtures(
        self,
        disposable_e2e_db: tuple[Session, sessionmaker[Session]],
        disposable_client: TestClient,
    ) -> None:
        """Verify complete flow: Fixture -> Normalizer -> Ingestion -> DB -> Catalog -> FastAPI."""
        session, _ = disposable_e2e_db
        IngestionService.seed_game_contexts(session)

        # Load fixtures
        clef_data = load_fixture("pokeapi_clefairy")
        pidg_data = load_fixture("pokeapi_pidgeot")
        geng_data = load_fixture("pokeapi_gengar")
        deox_data = load_fixture("pokeapi_deoxys_attack")

        # Ingest Clefairy (FireRed + Pokémon X)
        norm_clef_fr = PokeApiNormalizer.normalize_pokemon(
            clef_data["pokemon"], clef_data["species"], "firered"
        )
        norm_clef_x = PokeApiNormalizer.normalize_pokemon(
            clef_data["pokemon"], clef_data["species"], "pokemon-x"
        )
        IngestionService.ingest_pokemon(session, norm_clef_fr)
        IngestionService.ingest_pokemon(session, norm_clef_x)

        # Ingest Pidgeot (FireRed + Pokémon X)
        norm_pidg_fr = PokeApiNormalizer.normalize_pokemon(
            pidg_data["pokemon"], pidg_data["species"], "firered"
        )
        norm_pidg_x = PokeApiNormalizer.normalize_pokemon(
            pidg_data["pokemon"], pidg_data["species"], "pokemon-x"
        )
        IngestionService.ingest_pokemon(session, norm_pidg_fr)
        IngestionService.ingest_pokemon(session, norm_pidg_x)

        # Ingest Gengar (FireRed + Pokémon X)
        norm_geng_fr = PokeApiNormalizer.normalize_pokemon(
            geng_data["pokemon"], geng_data["species"], "firered"
        )
        norm_geng_x = PokeApiNormalizer.normalize_pokemon(
            geng_data["pokemon"], geng_data["species"], "pokemon-x"
        )
        IngestionService.ingest_pokemon(session, norm_geng_fr)
        IngestionService.ingest_pokemon(session, norm_geng_x)

        # Ingest Deoxys Attack (FireRed only)
        norm_deox_fr = PokeApiNormalizer.normalize_pokemon(
            deox_data["pokemon"], deox_data["species"], "firered"
        )
        IngestionService.ingest_pokemon(session, norm_deox_fr)

        # Ingest Unown (Unavailable in FireRed)
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
            abilities=(
                NormalizedAbilityAssignment(slot=1, ability_id="levitate", is_hidden=False),
            ),
            base_stats=NormalizedBaseStats(hp=48, atk=72, def_=48, spa=72, spd=48, spe=48),
            is_available=False,
        )
        IngestionService.ingest_pokemon(session, unavail_norm)
        session.commit()

        # 1. Search availability enforcement
        search_resp = disposable_client.get("/api/v1/pokemon?game_id=firered")
        assert search_resp.status_code == 200
        available_ids = [p["id"] for p in search_resp.json()]
        assert available_ids == ["pidgeot", "clefairy", "gengar", "deoxys-attack"]
        assert "unown" not in available_ids

        # 2. Clefairy Cross-Game Typing
        resp_clef_fr = disposable_client.get("/api/v1/pokemon/clefairy?game_id=firered")
        resp_clef_x = disposable_client.get("/api/v1/pokemon/clefairy?game_id=pokemon-x")
        assert resp_clef_fr.status_code == 200
        assert resp_clef_x.status_code == 200
        assert resp_clef_fr.json()["types"][0]["type_id"] == "normal"
        assert resp_clef_x.json()["types"][0]["type_id"] == "fairy"

        # 3. Pidgeot Cross-Game Stats & 'def' key
        resp_pidg_fr = disposable_client.get("/api/v1/pokemon/pidgeot?game_id=firered")
        resp_pidg_x = disposable_client.get("/api/v1/pokemon/pidgeot?game_id=pokemon-x")
        assert resp_pidg_fr.status_code == 200
        assert resp_pidg_x.status_code == 200
        assert resp_pidg_fr.json()["base_stats"]["spe"] == 91
        assert resp_pidg_x.json()["base_stats"]["spe"] == 101
        assert resp_pidg_fr.json()["base_stats"]["def"] == 75

        # 4. Gengar Ability
        resp_geng_fr = disposable_client.get("/api/v1/pokemon/gengar?game_id=firered")
        assert resp_geng_fr.status_code == 200
        assert resp_geng_fr.json()["abilities"][0]["ability_id"] == "levitate"

        # 5. Deoxys Attack Identity & Form
        resp_deox = disposable_client.get("/api/v1/pokemon/deoxys-attack?game_id=firered")
        assert resp_deox.status_code == 200
        deox = resp_deox.json()
        assert deox["dex_number"] == 386
        assert deox["form_name"] == "attack"
        assert deox["name"] == "Deoxys (Attack)"

        # 6. Error Handling
        assert disposable_client.get("/api/v1/pokemon").status_code == 422
        assert disposable_client.get("/api/v1/games/ruby/rules").status_code == 400
        assert (
            disposable_client.get("/api/v1/pokemon?game_id=firered&type_filter=fairy").status_code
            == 400
        )
        assert (
            disposable_client.get("/api/v1/pokemon/nonexistent?game_id=firered").status_code == 404
        )
        assert disposable_client.get("/api/v1/pokemon/unown?game_id=firered").status_code == 404
        assert disposable_client.get("/api/v1/pokemon?game_id=firered&limit=0").status_code == 422
