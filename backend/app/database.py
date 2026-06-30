from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os


# Load .env file (local development)
env_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    ".env"
)

load_dotenv(env_path)


# Use Render DATABASE_URL if available
# Otherwise fallback to SQLite database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./database.db"
)


print("DATABASE URL:", DATABASE_URL)


# SQLite needs special configuration
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={
            "check_same_thread": False
        }
    )

else:
    # PostgreSQL / other databases
    engine = create_engine(
        DATABASE_URL
    )


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()