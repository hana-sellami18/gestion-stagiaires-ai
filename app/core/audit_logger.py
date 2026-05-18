"""
Journal d'audit pour la conformité AI Act + RGPD.
Trace chaque analyse IA avec : horodatage, version modèle, score, justification.

Format double :
  - logs/audit.log    → texte lisible (debug, lecture humaine)
  - logs/audit.jsonl  → JSON Lines (parseable par outils, dashboards)
"""
import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger as base_logger


# Dossier des logs (créé automatiquement)
LOGS_DIR = Path(__file__).parent.parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

AUDIT_TEXT = LOGS_DIR / "audit.log"
AUDIT_JSON = LOGS_DIR / "audit.jsonl"


class AuditLogger:
    """Journalise chaque décision IA pour traçabilité et audit."""

    APP_VERSION = "1.0.0"
    SBERT_VERSION = "paraphrase-multilingual-MiniLM-L12-v2"
    LLM_VERSION = "llama3.1:8b"

    def log_cv_analysis(self, filename: str, cv_data: dict, duration_ms: float) -> str:
        """Trace une simple analyse de CV (sans scoring)."""
        audit_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()

        entry = {
            "audit_id": audit_id,
            "event": "CV_ANALYSIS",
            "timestamp": timestamp,
            "filename": filename,
            "filename_hash": self._hash(filename),
            "extraction_method": cv_data.get("extraction", {}).get("method"),
            "skills_count": cv_data.get("skills", {}).get("total", 0),
            "skills_found": cv_data.get("skills", {}).get("found_skills", []),
            "education_lines_count": len(cv_data.get("ner", {}).get("education_lines", [])),
            "duration_ms": round(duration_ms, 1),
            "app_version": self.APP_VERSION,
        }

        self._write(entry, summary=f"CV analysé : {filename} → {entry['skills_count']} compétences ({duration_ms:.0f}ms)")
        return audit_id

    def log_scoring(
        self,
        filename: str,
        subject_title: str,
        score_result,
        duration_ms: float,
    ) -> str:
        """Trace un scoring complet (CV vs sujet)."""
        audit_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()

        # Extraction des piliers (objet Pydantic → dict)
        pillars_data = {}
        for name, pillar in score_result.pillars.items():
            pillars_data[name] = {
                "score": pillar.score,
                "weight": pillar.weight,
                "weighted": pillar.weighted,
                "matched_count": len(pillar.matched),
                "missing_count": len(pillar.missing),
            }

        entry = {
            "audit_id": audit_id,
            "event": "SCORING",
            "timestamp": timestamp,
            "filename": filename,
            "filename_hash": self._hash(filename),
            "subject_title": subject_title,
            "final_score": score_result.final_score,
            "recommendation": score_result.recommendation,
            "pillars": pillars_data,
            "semantic_similarity": score_result.semantic_similarity,
            "duration_ms": round(duration_ms, 1),
            "app_version": self.APP_VERSION,
            "sbert_version": self.SBERT_VERSION,
        }

        summary = (
            f"Scoring : {filename} vs '{subject_title}' "
            f"→ {score_result.final_score}/100 [{score_result.recommendation}] "
            f"({duration_ms:.0f}ms)"
        )
        self._write(entry, summary=summary)
        return audit_id

    def log_interview_generation(
        self,
        filename: str,
        subject_title: str,
        questions_count: int,
        source: str,
        duration_ms: float,
    ) -> str:
        """Trace une génération de questions d'entretien."""
        audit_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()

        entry = {
            "audit_id": audit_id,
            "event": "INTERVIEW_GENERATION",
            "timestamp": timestamp,
            "filename": filename,
            "filename_hash": self._hash(filename),
            "subject_title": subject_title,
            "questions_count": questions_count,
            "source": source,  # 'llama' ou 'fallback'
            "duration_ms": round(duration_ms, 1),
            "app_version": self.APP_VERSION,
            "llm_version": self.LLM_VERSION if source == "llama" else None,
        }

        summary = (
            f"Questions : {filename} pour '{subject_title}' "
            f"→ {questions_count} questions [{source}] ({duration_ms:.0f}ms)"
        )
        self._write(entry, summary=summary)
        return audit_id

    def read_audit_log(self, limit: int = 50, event_filter: Optional[str] = None) -> list[dict]:
        """Lit les N derniers événements du journal JSON."""
        if not AUDIT_JSON.exists():
            return []

        with open(AUDIT_JSON, "r", encoding="utf-8") as f:
            lines = f.readlines()

        events = []
        # On lit du plus récent au plus ancien
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                if event_filter and event.get("event") != event_filter:
                    continue
                events.append(event)
                if len(events) >= limit:
                    break
            except json.JSONDecodeError:
                continue

        return events

    # ------------------------------------------------------------
    # Helpers privés
    # ------------------------------------------------------------
    def _write(self, entry: dict, summary: str):
        """Écrit dans les 2 fichiers + log console."""
        # 1) Fichier texte (lisible humain)
        with open(AUDIT_TEXT, "a", encoding="utf-8") as f:
            f.write(f"[{entry['timestamp']}] [{entry['audit_id']}] {summary}\n")

        # 2) Fichier JSONL (1 JSON par ligne, parseable)
        with open(AUDIT_JSON, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # 3) Console (loguru)
        base_logger.info(f"[AUDIT {entry['audit_id']}] {summary}")

    def _hash(self, text: str) -> str:
        """Hash SHA-256 court pour anonymiser les noms de fichiers (RGPD)."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


# Singleton
audit_logger = AuditLogger()