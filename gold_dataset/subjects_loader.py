"""
Loader unique des sujets de stage — source de vérité.
À utiliser PARTOUT (evaluate.py, auto_annotate.py, tests, etc.)
"""
import json
from pathlib import Path

from app.models.schemas import StageSubject

SUBJECTS_FILE = Path(__file__).parent / "subjects.json"


def load_subjects_dict() -> dict:
    """Retourne les sujets sous forme de dict brut (pour JSON)."""
    with open(SUBJECTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_subjects() -> dict[str, StageSubject]:
    """Retourne les sujets sous forme de StageSubject (objets Pydantic)."""
    raw = load_subjects_dict()
    return {sid: StageSubject(**sdef) for sid, sdef in raw.items()}