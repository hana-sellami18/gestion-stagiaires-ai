"""Endpoint de génération de questions d'entretien (avec audit)."""
import json
import time

from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from loguru import logger

from app.core.cv_parser import cv_parser
from app.core.interview_generator import interview_generator
from app.core.audit_logger import audit_logger
from app.models.schemas import StageSubject

router = APIRouter(prefix="/api/entretien", tags=["Interview"])


@router.post("/questions")
async def generate_interview_questions(
    file: UploadFile = File(..., description="CV en PDF"),
    subject: str = Form(..., description="Sujet de stage en JSON"),
):
    """Génère 9 questions d'entretien personnalisées."""
    # Parse subject
    try:
        subject_dict = json.loads(subject)
        stage_subject = StageSubject(**subject_dict)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON invalide : {e}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Sujet invalide : {e}")

    # Validation fichier
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Le fichier doit être un PDF")
    pdf_bytes = await file.read()
    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="Fichier vide")

    start = time.perf_counter()

    # Pipeline : Parse CV → Génère questions
    try:
        cv_data = cv_parser.parse(pdf_bytes)
    except Exception as e:
        logger.exception("Erreur parsing CV")
        raise HTTPException(status_code=500, detail=f"Erreur parsing CV : {e}")

    try:
        result = interview_generator.generate(cv_data, stage_subject)
    except Exception as e:
        logger.exception("Erreur génération questions")
        raise HTTPException(status_code=500, detail=f"Erreur génération : {e}")

    duration_ms = (time.perf_counter() - start) * 1000

    # 🔍 Audit
    audit_id = audit_logger.log_interview_generation(
        filename=file.filename,
        subject_title=stage_subject.title,
        questions_count=result.get("total", 0),
        source=result.get("source", "unknown"),
        duration_ms=duration_ms,
    )

    return {
        "audit_id": audit_id,
        "filename": file.filename,
        **result,
    }