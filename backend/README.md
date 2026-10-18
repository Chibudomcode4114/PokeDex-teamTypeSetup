# PokeDex TeamTypeMatchup - Backend

FastAPI backend service and core domain calculation engines.

## Requirements
- Python 3.11+ (Python 3.13 tested)
- SQLite (default local) or PostgreSQL

## Setup & Local Execution

1. **Activate Virtual Environment:**
   - On Windows (PowerShell):
     ```powershell
     .\.venv\Scripts\Activate.ps1
     ```
   - On Windows (cmd):
     ```cmd
     .venv\Scripts\activate.bat
     ```

2. **Environment Variables:**
   - Copy `.env.example` to `.env`:
     ```cmd
     copy .env.example .env
     ```
   - Defaults are preconfigured for local development with SQLite (`pokedex.db`).
   - For PostgreSQL, update `DATABASE_URL` in `.env`:
     ```env
     DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/pokedex
     ```

3. **Database Migrations:**
   - Check migration status:
     ```cmd
     alembic current
     ```
   - Apply migrations:
     ```cmd
     alembic upgrade head
     ```

4. **Database Seeding:**
   - Seed canonical game contexts (`firered`, `leafgreen`, `pokemon-x`, `pokemon-y`):
     ```cmd
     python -m app.db.seed_runner
     ```

5. **Disposable Database & Smoke Tests (Milestone 3C):**
   - Initialize and verify an isolated, disposable SQLite database without touching `pokedex.db`:
     ```powershell
     python scripts/verify_m3c.py
     ```
   - Manual disposable DB initialization commands:
     ```powershell
     $env:DATABASE_URL = "sqlite:///./disposable.db"
     alembic upgrade head
     python -m app.db.seed_runner
     ```

6. **Start the API Server:**
   ```cmd
   uvicorn app.main:app --reload --port 8000
   ```
   - Swagger Documentation: `http://localhost:8000/api/v1/docs`
   - ReDoc Documentation: `http://localhost:8000/api/v1/redoc`
   - Health Check: `http://localhost:8000/api/v1/health`

7. **Run Linting & Tests:**
   ```cmd
   ruff check .
   ruff format --check .
   pytest -v
   ```

## Catalog Population & Current Limitations

- **Current Status (M0–M3):**
  - Database schema, normalization layer, and catalog APIs are fully functional and verified.
  - The database is pre-seeded with MVP game contexts and generational rule profiles.
  - Representative Pokémon (`clefairy`, `pidgeot`, `gengar`, `deoxys-attack`) are verified across Gen III and Gen VI via deterministic offline fixtures.
- **Current Limitations:**
  - The catalog currently contains only seeded reference data and test fixtures.
  - An empty Pokémon search (`GET /api/v1/pokemon?game_id={id}`) returns `[]` until Pokémon are ingested for that game context.
- **Next Steps for Complete Game Pokédexes:**
  - Run the bulk ingestion pipeline to ingest the complete regional/national Pokédex for target games from PokeAPI.
  - Ingestion utilizes `PokeApiClient` (with rate-limiting and disk caching) and `PokeApiNormalizer` to populate `pokemon`, `pokemon_types`, `pokemon_abilities`, and `base_stats` per game context.
