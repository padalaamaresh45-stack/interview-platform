import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session as DBSession

from app.config import settings
from app.models.session import Session

SESSION_COOKIE_NAME = "session_id"


def create_session(db: DBSession, user_id: int) -> Session:
    session = Session(
        id=secrets.token_urlsafe(32),
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_valid_session(db: DBSession, session_id: str) -> Session | None:
    session = db.get(Session, session_id)
    if session is None:
        return None
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None
    return session


def delete_session(db: DBSession, session_id: str) -> None:
    session = db.get(Session, session_id)
    if session is not None:
        db.delete(session)
        db.commit()
