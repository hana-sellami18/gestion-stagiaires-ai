"""Endpoints d'analyse de CV et de scoring (avec audit)."""
import json
import time
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from loguru import logger

from app.core.cv_parser import cv_parser
from app.core.scorer import scorer
from app.core.audit_logger import audit_logger
from app.models.schemas import StageSubject, CompatibilityScore

router = APIRouter(prefix="/api/ia", tags=["CV Analysis"])


@router.post("/analyser-cv")
async def analyser_cv(file: UploadFile = File(...)):
    """Analyse un CV PDF et retourne les données structurées."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Le fichier doit être un PDF")

    pdf_bytes = await file.read()
    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="Fichier vide")

    start = time.perf_counter()
    try:
        result = cv_parser.parse(pdf_bytes)
    except Exception as e:
        logger.exception("Erreur lors de l'analyse du CV")
        raise HTTPException(status_code=500, detail=f"Erreur d'analyse : {e}")

    duration_ms = (time.perf_counter() - start) * 1000

    # 🔍 Audit
    audit_id = audit_logger.log_cv_analysis(file.filename, result, duration_ms)

    return {
        "audit_id": audit_id,
        "filename": file.filename,
        "size_bytes": len(pdf_bytes),
        **result,
    }


@router.post("/score-compatibilite", response_model=None)
async def score_compatibilite(
    file: UploadFile = File(..., description="CV en PDF"),
    subject: str = Form(..., description="Sujet de stage en JSON"),
):
    """Calcule le score de compatibilité entre un CV et un sujet de stage."""
    # 1) Parse subject JSON
    try:
        subject_dict = json.loads(subject)
        stage_subject = StageSubject(**subject_dict)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON invalide : {e}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Sujet invalide : {e}")

    # 2) Parse CV
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Le fichier doit être un PDF")
    pdf_bytes = await file.read()
    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="Fichier vide")

    start = time.perf_counter()
    try:
        cv_data = cv_parser.parse(pdf_bytes)
    except Exception as e:
        logger.exception("Erreur lors du parsing CV")
        raise HTTPException(status_code=500, detail=f"Erreur parsing CV : {e}")

    # 3) Scoring
    try:
        score_result = scorer.score(cv_data, stage_subject)
    except Exception as e:
        logger.exception("Erreur lors du scoring")
        raise HTTPException(status_code=500, detail=f"Erreur scoring : {e}")

    duration_ms = (time.perf_counter() - start) * 1000

    # 🔍 Audit
    audit_id = audit_logger.log_scoring(
        filename=file.filename,
        subject_title=stage_subject.title,
        score_result=score_result,
        duration_ms=duration_ms,
    )

    # 4) Infos CV pour affichage RH dans Angular
    cv_info = {
        "competences_detectees": cv_data.get("skills", {}).get("found_skills", []),
        "competences_par_categorie": cv_data.get("skills", {}).get("by_category", {}),
        "total_competences": cv_data.get("skills", {}).get("total", 0),
        "education_lines": cv_data.get("ner", {}).get("education_lines", []),
        "organisations": cv_data.get("ner", {}).get("organizations", []),
        "annees_detectees": cv_data.get("ner", {}).get("years", []),
        "extraction_method": cv_data.get("extraction", {}).get("method", ""),
        "num_pages": cv_data.get("extraction", {}).get("num_pages", 0),
        "anonymized": cv_data.get("anonymized", True),
    }

    # 5) Construction de la réponse finale
    return {
        "audit_id": audit_id,
        "filename": file.filename,
        "final_score": score_result.final_score,
        "recommendation": score_result.recommendation,
        "recommendation_label": score_result.recommendation_label,
        "pillars": {
            name: {
                "score": pillar.score,
                "weight": pillar.weight,
                "weighted": pillar.weighted,
                "matched": pillar.matched,
                "missing": pillar.missing,
            }
            for name, pillar in score_result.pillars.items()
        },
        "justification": score_result.justification,
        "semantic_similarity": score_result.semantic_similarity,
        "cv_info": cv_info,
    }