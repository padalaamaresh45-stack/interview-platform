from pydantic import BaseModel, Field


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=1, max_length=72)
