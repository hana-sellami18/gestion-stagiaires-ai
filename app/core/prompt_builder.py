"""
Construit les prompts pour LLaMA — génération de questions d'entretien.
"""
from app.models.schemas import StageSubject

SYSTEM_PROMPT = """Tu es un expert RH et technique chargé de préparer des entretiens de stage.
Tu génères des questions d'entretien personnalisées, pertinentes et professionnelles, en français.
Règles strictes :
- Tu DOIS répondre UNIQUEMENT en JSON valide, sans texte avant ou après.
- Les questions doivent être OUVERTES (pas oui/non).
- Les questions techniques doivent être basées sur les compétences réelles du candidat.
- Les questions comportementales doivent suivre le format STAR (Situation/Tâche/Action/Résultat).
- Adapte le niveau au profil : étudiant en stage, pas un senior.
- Pas de questions discriminatoires (âge, religion, origine, état civil)."""


def build_interview_prompt(cv_data: dict, subject: StageSubject) -> str:
    cv_skills = cv_data.get("skills", {}).get("found_skills", [])
    cv_skills_str = ", ".join(cv_skills[:20]) if cv_skills else "Aucune compétence détectée"

    education = cv_data.get("ner", {}).get("education_lines", [])
    education_str = "\n   - " + "\n   - ".join(education[:3]) if education else " Non précisée"

    cv_preview = cv_data.get("raw_text_preview", "")[:800]

    required_skills = ", ".join(subject.competences_cibles) if subject.competences_cibles else "Non précisées"

    prompt = f"""Génère exactement 9 questions d'entretien pour cette candidature.

SUJET DE STAGE :
- Titre : {subject.title}
- Description : {subject.description}
- Compétences requises : {required_skills}
- Filière : {subject.filiere or "Non précisée"}
- Cycle : {subject.cycle or "Non précisé"}

PROFIL DU CANDIDAT :
- Compétences détectées : {cv_skills_str}
- Formation :{education_str}

EXTRAIT DU CV :
{cv_preview}

CONSIGNES :
Génère 9 questions réparties ainsi :
- 3 questions TECHNIQUES (sur les compétences requises ET maîtrisées par le candidat)
- 2 questions PROJETS (basées sur les expériences/projets visibles dans le CV)
- 2 questions COMPORTEMENTALES (format STAR)
- 2 questions MOTIVATION (pourquoi ce stage, projet professionnel)

FORMAT DE SORTIE JSON STRICT :
{{
  "questions": [
    {{"category": "technique", "question": "..."}},
    {{"category": "technique", "question": "..."}},
    {{"category": "technique", "question": "..."}},
    {{"category": "projet", "question": "..."}},
    {{"category": "projet", "question": "..."}},
    {{"category": "comportementale", "question": "..."}},
    {{"category": "comportementale", "question": "..."}},
    {{"category": "motivation", "question": "..."}},
    {{"category": "motivation", "question": "..."}}
  ]
}}
Retourne UNIQUEMENT le JSON, rien d'autre."""
    return prompt


def get_system_prompt() -> str:
    return SYSTEM_PROMPT