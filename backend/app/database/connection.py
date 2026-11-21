
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import settings


engine = create_engine(
    settings.DATABASE_URL,
    echo=False
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def test_database_connection():

    with engine.connect() as connection:

        result = connection.execute(text("SELECT 1"))

        print("Database connection successful!")
        print("Result:", result.scalar())

def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()
