import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DEFAULT_DB_URL = "postgresql://postgres:postgres@localhost:5432/aarambham_db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

def create_db_engine(url):
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_size=10 if not url.startswith("sqlite") else 5,
        max_overflow=20 if not url.startswith("sqlite") else 10
    )

try:
    engine = create_db_engine(DATABASE_URL)
    # Test connection
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
except Exception as e:
    if "postgresql" in DATABASE_URL:
        print("\n" + "="*70, file=sys.stderr)
        print("⚠️ WARNING: Could not connect to PostgreSQL on localhost:5432.", file=sys.stderr)
        print("👉 Falling back to local SQLite database ('sqlite:///./aarambham_event.db') for instant testing.", file=sys.stderr)
        print("👉 To use PostgreSQL: ensure PostgreSQL service is started and database is created.", file=sys.stderr)
        print("="*70 + "\n", file=sys.stderr)
        DATABASE_URL = "sqlite:///./aarambham_event.db"
        engine = create_db_engine(DATABASE_URL)
    else:
        raise e

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

