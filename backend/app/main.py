from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="Interview Management Portal API")

app.include_router(health.router)
