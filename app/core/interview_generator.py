"""
Orchestrateur : CV + Sujet → 9 questions d'entretien.
"""
from loguru import logger

from app.core.llm_client import llm_client
from app.core.prompt_builder import build_interview_prompt, get_system_prompt
from app.models.schemas import StageSubject


# Catégories attendues pour vérifier la sortie LLaMA
EXPECTED_CATEGORIES = {
    "technique": 3,
    "projet": 2,
    "comportementale": 2,
    "motivation": 2,
}

# Fallback si LLaMA échoue : questions génériques
FALLBACK_QUESTIONS = [
    {"category": "technique", "question": "Quelle est la compétence technique que tu maîtrises le mieux et pourquoi ?"},
    {"category": "technique", "question": "Comment apprends-tu une nouvelle technologie ?"},
    {"category": "technique", "question": "Quelle est la dernière technologie que tu as apprise et comment l'as-tu utilisée ?"},
    {"category": "projet", "question": "Décris-moi le projet le plus complexe que tu as réalisé."},
    {"category": "projet", "question": "Quels ont été les principaux défis techniques rencontrés dans ce projet ?"},
    {"category": "comportementale", "question": "Décris une situation où tu as dû travailler en équipe sur un projet difficile. Quelle a été ta contribution ?"},
    {"category": "comportementale", "question": "Raconte-moi une fois où tu as dû gérer une deadline serrée. Comment t'y es-tu pris ?"},
    {"category": "motivation", "question": "Pourquoi as-tu choisi de postuler à ce stage en particulier ?"},
    {"category": "motivation", "question": "Où te vois-tu dans 3 ans professionnellement ?"},
]


class InterviewGenerator:
    """Génère 9 questions d'entretien personnalisées via LLaMA."""

    def generate(self, cv_data: dict, subject: StageSubject) -> dict:
        """
        Génère les questions d'entretien pour un candidat.

        :param cv_data: dict retourné par CVParser.parse()
        :param subject: sujet de stage
        :return: dict avec questions, métadonnées, et statut (LLM ou fallback)
        """
        prompt = build_interview_prompt(cv_data, subject)
        system = get_system_prompt()

        try:
            # Appel LLaMA
            logger.info("Génération des questions via LLaMA...")
            response = llm_client.generate_json(
                prompt=prompt,
                system=system,
                temperature=0.7,  # un peu de créativité, mais pas trop
            )

            questions = response.get("questions", [])

            # Validation de la structure
            if not self._validate_questions(questions):
                logger.warning("Questions LLaMA invalides → fallback")
                return self._fallback_response(subject)

            return {
                "questions": questions,
                "source": "llama",
                "model": llm_client.model,
                "subject_title": subject.title,
                "total": len(questions),
            }

        except Exception as e:
            logger.exception("Erreur génération LLaMA, fallback activé")
            return self._fallback_response(subject, error=str(e))

    def _validate_questions(self, questions: list) -> bool:
        """Vérifie que les questions ont la structure attendue."""
        if not isinstance(questions, list) or len(questions) < 7:
            return False
        for q in questions:
            if not isinstance(q, dict):
                return False
            if "category" not in q or "question" not in q:
                return False
            if not q["question"] or len(q["question"]) < 10:
                return False
        return True

    def _fallback_response(self, subject: StageSubject, error: str = None) -> dict:
        """Réponse de secours si LLaMA échoue."""
        return {
            "questions": FALLBACK_QUESTIONS,
            "source": "fallback",
            "model": None,
            "subject_title": subject.title,
            "total": len(FALLBACK_QUESTIONS),
            "warning": "LLaMA indisponible, questions génériques utilisées" + (f" (erreur: {error})" if error else ""),
        }


# Singleton
interview_generator = InterviewGenerator()