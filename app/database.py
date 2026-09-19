from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# Engine — database connection
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    echo=settings.debug,  # True hone pe SQL queries print hongi
)


# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    """
    FastAPI dependency — database session per request.
    
    Usage:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Saari tables create karo.
    Note: Production mein Alembic migrations use karo.
    """
    # Models import karo taake Base.metadata ko pata chale
    from app.models import user, meter, search  # noqa
    Base.metadata.create_all(bind=engine)