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

4. **Start the API Server:**
   ```cmd
   uvicorn app.main:app --reload --port 8000
   ```
   - Swagger Documentation: `http://localhost:8000/api/v1/docs`
   - ReDoc Documentation: `http://localhost:8000/api/v1/redoc`
   - Health Check: `http://localhost:8000/api/v1/health`

5. **Run Linting & Tests:**
   ```cmd
   ruff check .
   pytest -v
   ```
