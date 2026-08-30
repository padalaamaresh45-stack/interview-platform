from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import require_admin
from app.auth.hashing import hash_password
from app.database import get_db
from app.models.user import User
from app.schemas.user import ResetPasswordRequest

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


def _get_user_or_404(db: DBSession, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


@router.post("/{user_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    user_id: int,
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    user = _get_user_or_404(db, user_id)
    user.is_active = False
    db.commit()
    return None


@router.post("/{user_id}/reactivate", status_code=status.HTTP_204_NO_CONTENT)
def reactivate_user(
    user_id: int,
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    user = _get_user_or_404(db, user_id)
    user.is_active = True
    db.commit()
    return None


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: int,
    payload: ResetPasswordRequest,
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    user = _get_user_or_404(db, user_id)
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return None
