import os

from dotenv import load_dotenv
from sqlalchemy.engine import URL
from sqlmodel import Session, create_engine

load_dotenv()


def _resolve_database_url() -> str:
    """Resolve the database URL.

    Prefer an explicit DATABASE_URL (dev, tests, migration script). Otherwise
    build it from the discrete POSTGRES_* components via URL.create, which
    safely encodes special characters in the password — string interpolation
    in docker-compose would break on '@', ':' etc.
    """
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit

    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    database = os.getenv("POSTGRES_DB")
    if user and password and database:
        return URL.create(
            "postgresql+psycopg",
            username=user,
            password=password,
            host=os.getenv("DB_HOST", "db"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=database,
        ).render_as_string(hide_password=False)

    raise ValueError(
        "Set DATABASE_URL, or POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB."
    )


DATABASE_URL = _resolve_database_url()

# SQL echo is noisy and leaks data into logs; opt in explicitly via SQL_ECHO.
SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() in ("1", "true", "yes")

engine = create_engine(DATABASE_URL, echo=SQL_ECHO)


def get_session():
    with Session(engine) as session:
        yield session
