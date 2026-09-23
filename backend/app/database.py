"""SQLite database setup for the CAT Smart Operator Companion prototype."""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parents[1]          # backend/
PROJECT_DIR = BASE_DIR.parent                            # CAT-Operator-Companion/
DATA_DIR = PROJECT_DIR / "data"
DB_PATH = BASE_DIR / "operator_companion.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
