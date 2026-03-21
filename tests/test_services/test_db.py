from sqlalchemy import text
from sqlalchemy.orm import Session


def test_db_session_creates(db_session):
    assert isinstance(db_session, Session)
    result = db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1
