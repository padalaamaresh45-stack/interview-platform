from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    browser_timezone: str | None = None


class LoginResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    timezone: str | None
