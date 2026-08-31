from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import require_admin
from app.database import get_db
from app.models.position import Position
from app.models.question import Question
from app.models.user import User
from app.schemas.position import PositionCreate, PositionOut, PositionUpdate
from app.schemas.question import QuestionCreate, QuestionOut

router = APIRouter(prefix="/api/admin/positions", tags=["admin-positions"])


def _get_position_or_404(db: DBSession, position_id: int) -> Position:
    position = db.get(Position, position_id)
    if position is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found.")
    return position


def _to_position_out(position: Position, question_count: int) -> PositionOut:
    return PositionOut(
        id=position.id,
        title=position.title,
        question_count=question_count,
        created_at=position.created_at,
        updated_at=position.updated_at,
    )


def _count_questions(db: DBSession, position_id: int) -> int:
    return db.query(func.count(Question.id)).filter(Question.position_id == position_id).scalar()


@router.post("", response_model=PositionOut, status_code=status.HTTP_201_CREATED)
def create_position(
    payload: PositionCreate,
    db: DBSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    position = Position(title=payload.title, created_by=admin.id)
    db.add(position)
    db.commit()
    db.refresh(position)
    return _to_position_out(position, question_count=0)


@router.get("", response_model=list[PositionOut])
def list_positions(
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    rows = (
        db.query(Position, func.count(Question.id))
        .outerjoin(Question, Question.position_id == Position.id)
        .group_by(Position.id)
        .order_by(Position.id)
        .all()
    )
    return [_to_position_out(position, question_count) for position, question_count in rows]


@router.patch("/{position_id}", response_model=PositionOut)
def update_position(
    position_id: int,
    payload: PositionUpdate,
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    position = _get_position_or_404(db, position_id)
    position.title = payload.title
    db.commit()
    db.refresh(position)
    return _to_position_out(position, _count_questions(db, position.id))


@router.post("/{position_id}/questions", response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
def create_question(
    position_id: int,
    payload: QuestionCreate,
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    _get_position_or_404(db, position_id)
    question = Question(
        position_id=position_id,
        question_text=payload.question_text,
        sequence_order=payload.sequence_order,
    )
    db.add(question)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A question already exists at sequence_order {payload.sequence_order} for this position.",
        )
    db.refresh(question)
    return question


@router.get("/{position_id}/questions", response_model=list[QuestionOut])
def list_questions(
    position_id: int,
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    _get_position_or_404(db, position_id)
    return (
        db.query(Question)
        .filter(Question.position_id == position_id)
        .order_by(Question.sequence_order)
        .all()
    )
