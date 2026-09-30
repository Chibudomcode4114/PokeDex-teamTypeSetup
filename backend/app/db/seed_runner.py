"""Database seed runner script for initial game contexts and reference data."""

from app.db.session import SessionLocal
from app.services.ingestion_service import IngestionService


def run_seed() -> None:
    """Run database seeding for canonical game contexts."""
    with SessionLocal() as session:
        IngestionService.seed_game_contexts(session)
        session.commit()


if __name__ == "__main__":
    run_seed()
