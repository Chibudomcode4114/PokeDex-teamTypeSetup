"""End-to-End Verification and Smoke Test Runner (Milestone 3C).

Initializes a fresh disposable SQLite database using Alembic migrations,
runs game context seeding, tests unseeded catalog responses, ingests
representative PokeAPI fixtures, and validates all catalog endpoints,
game-divergence rules, and error contracts.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any

# Ensure backend root is on sys.path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from alembic import command  # noqa: E402
from app.adapters.pokeapi.normalizer import PokeApiNormalizer  # noqa: E402
from app.adapters.pokeapi.schemas import (  # noqa: E402
    NormalizedAbilityAssignment,
    NormalizedBaseStats,
    NormalizedPokemon,
    NormalizedTypeAssignment,
)
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.game_service import GameCatalogService  # noqa: E402
from app.services.ingestion_service import IngestionService  # noqa: E402

FIXTURES_DIR = BACKEND_ROOT / "tests" / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    """Load JSON fixture from local test fixtures."""
    path = FIXTURES_DIR / f"{name}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_e2e_verification() -> bool:
    """Execute complete Milestone 3C end-to-end verification."""
    temp_dir = Path(tempfile.gettempdir())
    db_name = f"m3c_disposable_{uuid.uuid4().hex[:8]}.db"
    db_path = temp_dir / db_name
    db_url = f"sqlite:///{db_path}"

    print("\n=======================================================")
    print(" Milestone 3C: End-to-End Catalog Verification")
    print("=======================================================")
    print(f"Disposable SQLite DB: {db_path}")

    # Set environment variable so any child components resolve this database
    os.environ["DATABASE_URL"] = db_url

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    disposable_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db() -> Generator[Session]:
        session = disposable_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        # ------------------------------------------------------------------
        # 1. Database Initialization via Alembic Migrations
        # ------------------------------------------------------------------
        print("\n--- Step 1: Database Initialization via Alembic ---")
        alembic_ini_path = BACKEND_ROOT / "alembic.ini"
        alembic_cfg = Config(str(alembic_ini_path))
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        alembic_cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))

        command.upgrade(alembic_cfg, "head")
        assert db_path.exists(), "Disposable database file was not created by Alembic."
        print(" [PASS] Alembic migrations upgraded to head: schema initialized.")

        # ------------------------------------------------------------------
        # 2. Game Context Seeding
        # ------------------------------------------------------------------
        print("\n--- Step 2: Game Context Seeding ---")
        with disposable_session_factory() as session:
            IngestionService.seed_game_contexts(session)
            session.commit()

            games = GameCatalogService.get_games(session)
            game_ids = [g.id for g in games]
            print(f" Seeded games in database: {game_ids}")
            assert game_ids == ["firered", "leafgreen", "pokemon-x", "pokemon-y"], (
                f"Unexpected games: {game_ids}"
            )
            assert all(g.is_supported for g in games), "Not all games are marked is_supported=True."
        print(" [PASS] 4 supported MVP games successfully seeded in database.")

        # ------------------------------------------------------------------
        # 3. Real Application Smoke Tests (Unseeded Catalog)
        # ------------------------------------------------------------------
        print("\n--- Step 3: Application Smoke Tests (Unseeded Catalog) ---")
        with TestClient(app) as client:
            # 3a. Health Check
            resp_health = client.get("/api/v1/health")
            print(f" GET /api/v1/health -> {resp_health.status_code}: {resp_health.json()}")
            assert resp_health.status_code == 200
            assert resp_health.json()["status"] == "ok"

            # 3b. Games List
            resp_games = client.get("/api/v1/games")
            print(f" GET /api/v1/games -> {resp_games.status_code}: {len(resp_games.json())} games")
            assert resp_games.status_code == 200
            assert len(resp_games.json()) == 4

            # 3c. Rules for FireRed
            resp_fr_rules = client.get("/api/v1/games/firered/rules")
            fr_rules = resp_fr_rules.json()
            print(
                f" GET /api/v1/games/firered/rules -> {resp_fr_rules.status_code} "
                f"(Gen {fr_rules['generation']}, {fr_rules['type_chart_version']})"
            )
            assert resp_fr_rules.status_code == 200
            assert resp_fr_rules.json()["mechanic_flags"]["has_fairy_type"] is False

            # 3d. Rules for Pokémon X
            resp_x_rules = client.get("/api/v1/games/pokemon-x/rules")
            x_rules = resp_x_rules.json()
            print(
                f" GET /api/v1/games/pokemon-x/rules -> {resp_x_rules.status_code} "
                f"(Gen {x_rules['generation']}, {x_rules['type_chart_version']})"
            )
            assert resp_x_rules.status_code == 200
            assert resp_x_rules.json()["mechanic_flags"]["has_fairy_type"] is True

            # 3e. Pokémon search with empty catalog (should return [] rather than error)
            resp_empty_search = client.get("/api/v1/pokemon?game_id=firered")
            print(f" GET /api/v1/pokemon?game_id=firered -> {resp_empty_search.status_code}: []")
            assert resp_empty_search.status_code == 200
            assert resp_empty_search.json() == []
        print(" [PASS] Smoke tests passed: unseeded catalog search cleanly returns [].")

        # ------------------------------------------------------------------
        # 4. Fixture Ingestion & Normalization
        # ------------------------------------------------------------------
        print("\n--- Step 4: Fixture Normalization & Ingestion ---")
        clef_data = load_fixture("pokeapi_clefairy")
        pidg_data = load_fixture("pokeapi_pidgeot")
        geng_data = load_fixture("pokeapi_gengar")
        deox_data = load_fixture("pokeapi_deoxys_attack")

        with disposable_session_factory() as session:
            # Clefairy
            norm_clef_fr = PokeApiNormalizer.normalize_pokemon(
                clef_data["pokemon"], clef_data["species"], "firered"
            )
            norm_clef_x = PokeApiNormalizer.normalize_pokemon(
                clef_data["pokemon"], clef_data["species"], "pokemon-x"
            )
            IngestionService.ingest_pokemon(session, norm_clef_fr)
            IngestionService.ingest_pokemon(session, norm_clef_x)

            # Pidgeot
            norm_pidg_fr = PokeApiNormalizer.normalize_pokemon(
                pidg_data["pokemon"], pidg_data["species"], "firered"
            )
            norm_pidg_x = PokeApiNormalizer.normalize_pokemon(
                pidg_data["pokemon"], pidg_data["species"], "pokemon-x"
            )
            IngestionService.ingest_pokemon(session, norm_pidg_fr)
            IngestionService.ingest_pokemon(session, norm_pidg_x)

            # Gengar
            norm_geng_fr = PokeApiNormalizer.normalize_pokemon(
                geng_data["pokemon"], geng_data["species"], "firered"
            )
            norm_geng_x = PokeApiNormalizer.normalize_pokemon(
                geng_data["pokemon"], geng_data["species"], "pokemon-x"
            )
            IngestionService.ingest_pokemon(session, norm_geng_fr)
            IngestionService.ingest_pokemon(session, norm_geng_x)

            # Deoxys Attack (FireRed only)
            norm_deox_fr = PokeApiNormalizer.normalize_pokemon(
                deox_data["pokemon"], deox_data["species"], "firered"
            )
            IngestionService.ingest_pokemon(session, norm_deox_fr)

            # Unown (Unavailable in FireRed)
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
        print(" [PASS] 5 test Pokémon successfully ingested through pure normalizer.")

        # ------------------------------------------------------------------
        # 5. Post-Ingestion Catalog Retrieval & Cross-Game Divergence
        # ------------------------------------------------------------------
        print("\n--- Step 5: Post-Ingestion API Assertions ---")
        with TestClient(app) as client:
            # 5a. Search in FireRed (Unown must be excluded)
            resp_search_fr = client.get("/api/v1/pokemon?game_id=firered")
            assert resp_search_fr.status_code == 200
            fr_ids = [p["id"] for p in resp_search_fr.json()]
            print(f" FireRed available Pokémon: {fr_ids}")
            assert fr_ids == ["pidgeot", "clefairy", "gengar", "deoxys-attack"]
            assert "unown" not in fr_ids

            # 5b. Clefairy Cross-Game Typing
            resp_clef_fr = client.get("/api/v1/pokemon/clefairy?game_id=firered")
            resp_clef_x = client.get("/api/v1/pokemon/clefairy?game_id=pokemon-x")
            assert resp_clef_fr.status_code == 200
            assert resp_clef_x.status_code == 200
            clef_fr_type = resp_clef_fr.json()["types"][0]["type_id"]
            clef_x_type = resp_clef_x.json()["types"][0]["type_id"]
            print(f" Clefairy Typing: FireRed={clef_fr_type}, Pokémon X={clef_x_type}")
            assert clef_fr_type == "normal"
            assert clef_x_type == "fairy"

            # 5c. Pidgeot Cross-Game Stats Divergence & Base Stats 'def' serialization
            resp_pidg_fr = client.get("/api/v1/pokemon/pidgeot?game_id=firered")
            resp_pidg_x = client.get("/api/v1/pokemon/pidgeot?game_id=pokemon-x")
            assert resp_pidg_fr.status_code == 200
            assert resp_pidg_x.status_code == 200
            spe_fr = resp_pidg_fr.json()["base_stats"]["spe"]
            spe_x = resp_pidg_x.json()["base_stats"]["spe"]
            def_fr = resp_pidg_fr.json()["base_stats"]["def"]
            print(f" Pidgeot Speed: FireRed={spe_fr}, Pokémon X={spe_x} | Defense key: {def_fr}")
            assert spe_fr == 91
            assert spe_x == 101
            assert def_fr == 75

            # 5d. Gengar Abilities
            resp_geng_fr = client.get("/api/v1/pokemon/gengar?game_id=firered")
            assert resp_geng_fr.status_code == 200
            geng_abilities = [a["ability_id"] for a in resp_geng_fr.json()["abilities"]]
            print(f" Gengar Abilities: {geng_abilities}")
            assert "levitate" in geng_abilities

            # 5e. Deoxys Attack Form Identity
            resp_deox = client.get("/api/v1/pokemon/deoxys-attack?game_id=firered")
            assert resp_deox.status_code == 200
            deox_data = resp_deox.json()
            print(
                f" Deoxys Identity: Dex={deox_data['dex_number']}, "
                f"Species={deox_data['species_name']}, Form={deox_data['form_name']}"
            )
            assert deox_data["dex_number"] == 386
            assert deox_data["form_name"] == "attack"
            assert deox_data["name"] == "Deoxys (Attack)"
        print(" [PASS] Post-ingestion API retrieval verified across games.")

        # ------------------------------------------------------------------
        # 6. Error Handling Contracts
        # ------------------------------------------------------------------
        print("\n--- Step 6: Error Handling Contracts ---")
        with TestClient(app) as client:
            # 6a. Missing game context -> 422
            r1 = client.get("/api/v1/pokemon")
            print(f" Missing game_id: status={r1.status_code} (expected 422)")
            assert r1.status_code == 422

            # 6b. Unsupported game -> 400
            r2 = client.get("/api/v1/games/ruby/rules")
            print(f" Unsupported game: status={r2.status_code} (expected 400)")
            assert r2.status_code == 400

            # 6c. Unsupported type for game -> 400
            r3 = client.get("/api/v1/pokemon?game_id=firered&type_filter=fairy")
            print(f" Unsupported type (Fairy in FireRed): status={r3.status_code} (expected 400)")
            assert r3.status_code == 400

            # 6d. Unknown Pokémon -> 404
            r4 = client.get("/api/v1/pokemon/nonexistent-mon?game_id=firered")
            print(f" Unknown Pokémon: status={r4.status_code} (expected 404)")
            assert r4.status_code == 404

            # 6e. Unavailable Pokémon in game -> 404
            r5 = client.get("/api/v1/pokemon/unown?game_id=firered")
            print(
                f" Unavailable Pokémon (Unown in FireRed): status={r5.status_code} (expected 404)"
            )
            assert r5.status_code == 404

            # 6f. Invalid pagination -> 422
            r6 = client.get("/api/v1/pokemon?game_id=firered&limit=0")
            print(f" Invalid pagination (limit=0): status={r6.status_code} (expected 422)")
            assert r6.status_code == 422
        print(" [PASS] All error handling contracts verified.")

        print("\n=======================================================")
        print(" ALL MILESTONE 3C VERIFICATIONS PASSED SUCCESSFULLY")
        print("=======================================================\n")
        return True

    finally:
        # Reset dependency overrides
        app.dependency_overrides.clear()
        # Clean up disposable database
        engine.dispose()
        if db_path.exists():
            try:
                db_path.unlink()
                print(f"Cleaned up disposable database: {db_path}")
            except Exception as e:
                print(f"Warning: could not delete {db_path}: {e}")


if __name__ == "__main__":
    success = run_e2e_verification()
    sys.exit(0 if success else 1)
