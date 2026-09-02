from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import admin_candidates, admin_positions, admin_questions, admin_users, auth, health, interviewer

app = FastAPI(title="Interview Management Portal API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin_users.router)
app.include_router(admin_positions.router)
app.include_router(admin_questions.router)
app.include_router(admin_candidates.router)
app.include_router(admin_candidates.interviewers_router)
app.include_router(interviewer.router)
