from datetime import datetime

from pydantic import BaseModel, Field


class PositionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class PositionUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class PositionOut(BaseModel):
    id: int
    title: str
    question_count: int
    candidate_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
