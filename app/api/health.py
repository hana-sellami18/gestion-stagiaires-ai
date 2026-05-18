"""Endpoint de healthcheck — vérifie que l'API et ses dépendances sont OK."""
from fastapi import APIRouter
import httpx
from app.config import settings

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/")
async def health_check():
    """Retourne l'état de l'API."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/ollama")
async def ollama_check():
    """Vérifie qu'Ollama répond et que le modèle est disponible."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{settings.ollama_host}/api/tags")
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            llama_present = any(settings.ollama_model in m for m in models)
            return {
                "status": "ok" if llama_present else "model_missing",
                "ollama_running": True,
                "expected_model": settings.ollama_model,
                "available_models": models,
            }
    except Exception as e:
        return {
            "status": "error",
            "ollama_running": False,
            "error": str(e),
        }