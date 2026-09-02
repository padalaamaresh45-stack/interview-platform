from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import get_current_user
from app.auth.hashing import verify_password
from app.auth.session import SESSION_COOKIE_NAME, create_session, delete_session
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

_GENERIC_LOGIN_ERROR = "Invalid email or password."


@router.get("/me", response_model=LoginResponse)
def me(user: User = Depends(get_current_user)):
    return LoginResponse(id=user.id, email=user.email, full_name=user.full_name, role=user.role.value)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_GENERIC_LOGIN_ERROR)

    session = create_session(db, user.id)

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session.id,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_hours * 3600,
    )

    return LoginResponse(id=user.id, email=user.email, full_name=user.full_name, role=user.role.value)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: DBSession = Depends(get_db),
):
    if session_id is not None:
        delete_session(db, session_id)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return None
