"""Schema creation and first-run seeding.

`create_all` is deliberate for a prototype: the schema is young and reset often.
Alembic is installed and configured for when the schema stabilises.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import User, Vehicle  # noqa: F401 - registers the tables
from app.models.enums import UserRole

logger = logging.getLogger(__name__)

DEMO_VEHICLES = [
    {"registration": "CBA-4471", "make": "Toyota", "model": "Aqua", "year": 2019,
     "colour": "Pearl White", "body_type": "Hatchback"},
    {"registration": "CAR-8820", "make": "Suzuki", "model": "Wagon R", "year": 2021,
     "colour": "Silver", "body_type": "Hatchback"},
    {"registration": "KX-1093", "make": "Honda", "model": "Vezel", "year": 2018,
     "colour": "Midnight Blue", "body_type": "SUV"},
    {"registration": "CBB-2255", "make": "Nissan", "model": "Leaf", "year": 2020,
     "colour": "Black", "body_type": "Hatchback"},
    {"registration": "CAF-7710", "make": "Toyota", "model": "Premio", "year": 2017,
     "colour": "Silver", "body_type": "Saloon"},
]


def create_tables() -> None:
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def seed(db: Session) -> None:
    if db.execute(select(User).limit(1)).scalar_one_or_none() is None:
        admin = User(
            email=settings.FIRST_ADMIN_EMAIL.strip().lower(),
            full_name="System Administrator",
            hashed_password=hash_password(settings.FIRST_ADMIN_PASSWORD),
            role=UserRole.ADMIN,
        )
        inspector = User(
            email="inspector@drivetime.lk",
            full_name="Ravindu Perera",
            hashed_password=hash_password("Inspector123!"),
            role=UserRole.INSPECTOR,
        )
        db.add_all([admin, inspector])
        db.commit()
        logger.info("Seeded admin account: %s", admin.email)

    if settings.SEED_DEMO_DATA:
        if db.execute(select(Vehicle).limit(1)).scalar_one_or_none() is None:
            db.add_all(Vehicle(**data) for data in DEMO_VEHICLES)
            db.commit()
            logger.info("Seeded %d demo vehicles", len(DEMO_VEHICLES))


def init_db() -> None:
    create_tables()
    with SessionLocal() as db:
        seed(db)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("Database initialised.")
