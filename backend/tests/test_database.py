import pytest
from app.db.database import get_db
from app.db.session import SessionLocal, engine


class TestDatabase:
    def test_get_db_generator(self):
        gen = get_db()

        db = next(gen)

        assert db is not None
        assert db.is_active

        try:
            next(gen)
        except StopIteration:
            pass

    def test_session_local_creation(self):
        session = SessionLocal()

        assert session is not None
        session.close()

    def test_engine_creation(self):
        assert engine is not None
        assert engine.url is not None
