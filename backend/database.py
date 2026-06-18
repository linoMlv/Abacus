import os

from dotenv import load_dotenv
from sqlmodel import Session, create_engine

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# SQL echo is noisy and leaks data into logs; opt in explicitly via SQL_ECHO.
SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() in ("1", "true", "yes")

engine = create_engine(DATABASE_URL, echo=SQL_ECHO)


def get_session():
    with Session(engine) as session:
        yield session
