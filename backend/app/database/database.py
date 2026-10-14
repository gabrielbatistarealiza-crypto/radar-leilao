from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não configurada.")


engine = create_engine(DATABASE_URL)

if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def _register_translate(connection, _record):
        def translate(value, source_chars, target_chars):
            if value is None:
                return None
            replacements = dict(zip(source_chars, target_chars))
            return "".join(replacements.get(char, char) for char in value)

        connection.create_function("translate", 3, translate)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
