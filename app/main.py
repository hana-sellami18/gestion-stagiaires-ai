"""Point d'entrée FastAPI du module IA ASM."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import health, cv, interview ,audit

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Module IA d'analyse de CVs pour ASM",
)

# CORS — autorise Spring Boot et Angular à appeler l'API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # à restreindre en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router)
app.include_router(cv.router)
app.include_router(interview.router)
app.include_router(audit.router)




@app.get("/")
async def root():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }