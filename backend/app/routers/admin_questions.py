from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.auth.dependencies import require_admin
from app.database import get_db
from app.models.interview_score import InterviewScore
from app.models.question import Question
from app.models.user import User
from app.schemas.question import QuestionOut, QuestionUpdate

router = APIRouter(prefix="/api/admin/questions", tags=["admin-questions"])


def _get_question_or_404(db: DBSession, question_id: int) -> Question:
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found.")
    return question


@router.patch("/{question_id}", response_model=QuestionOut)
def update_question(
    question_id: int,
    payload: QuestionUpdate,
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    question = _get_question_or_404(db, question_id)
    question.question_text = payload.question_text
    db.commit()
    db.refresh(question)
    return question


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    question_id: int,
    db: DBSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    question = _get_question_or_404(db, question_id)
    score_count = db.query(InterviewScore).filter(InterviewScore.question_id == question_id).count()
    if score_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete question {question_id}: {score_count} scores already recorded against it.",
        )
    db.delete(question)
    db.commit()
    return None
