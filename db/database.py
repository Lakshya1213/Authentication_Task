"""
SQLAlchemy engine, session factory, and database initialization.

Provides a request-scoped DB session via FastAPI dependency injection.
"""

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def get_db():
    """
    Yield a database session and ensure it is closed after the request.

    Usage in routes:
        def my_route(db: Session = Depends(get_db)): ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables defined on Base.metadata (idempotent for POC)."""
    # Import models so they register with Base.metadata before create_all
    import models  # noqa: F401

    logger.info("Initializing database tables")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ready")
