from datetime import datetime

from pydantic import BaseModel, Field


class QuestionCreate(BaseModel):
    question_text: str = Field(min_length=1)
    sequence_order: int = Field(ge=0)


class QuestionUpdate(BaseModel):
    question_text: str = Field(min_length=1)


class QuestionOut(BaseModel):
    id: int
    position_id: int
    question_text: str
    sequence_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
