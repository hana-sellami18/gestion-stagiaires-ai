"""
================================================================================
LLM CV EXTRACTOR v3 — Prompt explicite anti-sous-comptage
================================================================================

CHANGEMENTS v3 :
- Prompt PLUS EXPLICITE pour eviter le sous-comptage (llama-3.3-70b est tres
  conservateur et rate parfois des stages clairs comme "Internship Project"
  ou "PFE — Academic Project")
- AJOUT d'exemples CONCRETS dans le prompt
- AJOUT de la regle : "Internship" dans le titre = TOUJOURS un stage
- AJOUT de la regle : "PFE" dans le titre = TOUJOURS un stage (meme si
  etiquete "Academic Project")
================================================================================
"""

from typing import Dict, Any
from loguru import logger

from app.core.llm_client import llm_client


# =============================================================================
# CONFIGURATION
# =============================================================================
LLM_TEMPERATURE = 0.0
MAX_CV_LENGTH = 4500


# =============================================================================
# PROMPT SYSTEME
# =============================================================================
SYSTEM_PROMPT = """Tu es un expert RH specialise dans l'analyse de CV d'etudiants tunisiens en informatique.
Tu reponds TOUJOURS et UNIQUEMENT avec un JSON valide.
Tu es FACTUEL et tu COMPTES correctement, sans sous-evaluer ni sur-evaluer."""


# =============================================================================
# PROMPT D'EXTRACTION v3 — Plus explicite
# =============================================================================
EXTRACTION_PROMPT = """Analyse ce CV et extrait les informations au format JSON.

CV a analyser :
\"\"\"
{cv_text}
\"\"\"

Reponds avec ce JSON EXACT :
{{
  "nombre_stages": <entier>,
  "entreprises_de_stage": ["NomEntreprise1", "NomEntreprise2"],
  "cycle": "licence" ou "master" ou "ingenieur" ou "autre",
  "annee_etude": <entier 1-5 ou null>,
  "is_pfe": true ou false,
  "has_pfe_project": true ou false,
  "soft_skills": ["leadership", "communication", ...],
  "projets_count": <entier>,
  "has_github": true ou false,
  "specialite_dominante": "backend" ou "frontend" ou "fullstack" ou "mobile" ou "data" ou "ai" ou "devops" ou "autre"
}}

============================================================
REGLES POUR COMPTER LES STAGES (TRES IMPORTANT)
============================================================

UN BLOC = UN STAGE si TOUT ce qui suit est vrai :
A) Il contient une DATE (ex: "06/2024", "Jun 2025 - Jul 2025", "2024-2025")
B) Il contient au moins UN de ces MOTS-CLES FORTS :
   - "stage" / "stagiaire"
   - "internship" / "intern"
   - "PFE" / "PFA"
   - "projet de fin d'etudes"
   OU
   Il liste UNE ENTREPRISE NOMMEE (Primatec, ASM, Comptoir Hammemi, Sofrecom...)

REGLES STRICTES (NE PAS DEVIER) :
- Si tu vois "Internship Project" -> C'EST UN STAGE (compte +1)
- Si tu vois "PFE" ou "Projet de Fin d'Etudes" -> C'EST UN STAGE (compte +1)
  MEME SI le titre dit aussi "Academic Project" ou "Final Year Project"
- Si tu vois "1. NomEntreprise" suivi d'une date -> C'EST UN STAGE
- Si tu vois plusieurs entreprises numerotees (1. X, 2. Y, 3. Z) -> COMPTE-LES TOUTES

EXEMPLES CONCRETS :

CV 1 : "Delivery App Internship Project, June 2025 - July 2025"
       + "Backend Developer | WEDTECT (PFE — Academic Project) Feb 2026"
       -> nombre_stages = 2 (le mot 'Internship' ET le mot 'PFE')
       -> entreprises_de_stage = ["WEDTECT"] (si Delivery App est sans entreprise nommee)

CV 2 : "1. Primatec - 06/2024"
       "2. ASM - 07/2024"
       "3. ASM - 07/2025"
       "4. ASM - 02/2026 - 07/2026"
       -> nombre_stages = 4 (quatre blocs entreprise+date)
       -> entreprises_de_stage = ["Primatec", "ASM"]

CV 3 : "TunisiaFlicks - Movie App Personal Project"
       "E-commerce Website Personal Project"
       -> nombre_stages = 0 (ce sont des projets perso, pas des stages)
       -> entreprises_de_stage = []

NE COMPTE PAS COMME STAGE :
- "Personal Project" SEUL (sans Internship/PFE/entreprise)
- "Mobile Department Leader, Google Club" -> c'est un club, pas un stage
- "Hackathon", "Competition" -> ce sont des evenements

============================================================
REGLES POUR LES ENTREPRISES
============================================================

entreprises_de_stage = SOCIETES qui ont employe le candidat
Exemples : "Sofrecom", "Talan", "Vermeg", "ASM", "Primatec", "Comptoir Hammemi", "WEDTECT"

NE PAS METTRE :
- Noms de TECHNOLOGIES : JWT, OAuth, MVC, REST, React, Spring, Node.js...
- Noms d'ECOLES : ISIMS, ENIT, ENIS, IIT
- Noms de CLUBS : Google Club, IEEE, AWS Club
- Noms de PROJETS perso : TunisiaFlicks, MyPortfolio, Angry Birds

============================================================
REGLES POUR LE CYCLE
============================================================

- "Licence en informatique" / "Diploma in Computer Science" -> "licence" (3 ans)
- "Master" / "M1" / "M2" / "Mastere" -> "master" (2 ans)
- "Cycle ingenieur" / "Genie informatique" SEUL -> "ingenieur"
- "Genie logiciel" + "Systemes d'information" (specialite tunisienne) -> "licence"
- "GLSI" (acronyme IIT Sfax) -> "licence"

============================================================
ANNEE_ETUDE et IS_PFE
============================================================

annee_etude = numero d'annee dans le cycle (1, 2, 3, 4, 5)
- Si tu vois "3eme annee" / "L3" / "third year" -> annee_etude = 3
- Si tu vois SEULEMENT les dates ex "Sep 2023 - June 2026" :
  -> Calcule : annee_courante - date_debut + 1
  -> Ex: 2026 - 2023 + 1 = 4eme annee... mais cycle de 3 ans -> donc annee=3 (derniere)

is_pfe = true si :
- Licence + annee 3 -> TRUE
- Master + annee 2 -> TRUE
- Ingenieur + annee 3 (cycle court) ou 5 (cycle long) -> TRUE

============================================================
SOFT SKILLS et PROJETS
============================================================

soft_skills : extrais ceux EXPLICITEMENT mentionnes
- "leadership" si "club leader", "team leader"
- "teamwork" si "team project", "collaboration", "travail en equipe"
- "communication" si mentionne explicitement
- "autonomie", "rigueur", "organisation" si mentionnes

projets_count : compte les projets perso + academiques + PFE
PAS les stages, PAS les hackathons/competitions.

============================================================

Reponds maintenant UNIQUEMENT avec le JSON :"""


# =============================================================================
# VALEUR PAR DEFAUT
# =============================================================================
DEFAULT_EXTRACTION = {
    "nombre_stages": None,
    "entreprises_de_stage": [],
    "cycle": "autre",
    "annee_etude": None,
    "is_pfe": False,
    "has_pfe_project": False,
    "soft_skills": [],
    "projets_count": None,
    "has_github": False,
    "specialite_dominante": "autre",
    "_llm_available": False,
}


# =============================================================================
# LISTE DE TECHNOLOGIES (anti-hallucination)
# =============================================================================
TECH_NOT_COMPANIES = {
    "jwt", "oauth", "oauth2", "oauth 2.0", "rest", "rest api", "graphql",
    "react", "react.js", "angular", "vue", "vue.js", "next.js", "nuxt",
    "node.js", "nodejs", "express", "nest.js", "nestjs",
    "spring", "spring boot", "django", "flask", "laravel", "symfony",
    "mongodb", "mongoose", "mysql", "postgresql", "redis", "elasticsearch",
    "docker", "kubernetes", "aws", "azure", "gcp",
    "git", "github", "gitlab", "bitbucket",
    "python", "java", "javascript", "typescript", "c#", "c++",
    "html", "css", "sass", "tailwind",
    "flutter", "dart", "kotlin", "swift",
    "tensorflow", "pytorch", "scikit-learn",
    "socket.io", "websocket", "websockets",
    "nodemailer", "passport.js", "passport",
    "groq", "openai", "llama", "anthropic",
    "vite", "webpack", "babel",
    "linux", "windows", "macos",
    "mvc", "mvvm",
}


# =============================================================================
# VALIDATION ET NETTOYAGE
# =============================================================================
def _validate_and_clean(data: Dict[str, Any]) -> Dict[str, Any]:
    """Valide les champs et nettoie les hallucinations courantes."""
    result = DEFAULT_EXTRACTION.copy()

    # nombre_stages
    val = data.get("nombre_stages")
    if isinstance(val, int) and 0 <= val <= 20:
        result["nombre_stages"] = val
    elif isinstance(val, str) and val.isdigit():
        result["nombre_stages"] = min(int(val), 20)

    # entreprises_de_stage
    val = data.get("entreprises_de_stage", [])
    if isinstance(val, list):
        cleaned_entreprises = []
        for e in val:
            if not e or not isinstance(e, str):
                continue
            e_clean = str(e).strip()
            e_lower = e_clean.lower()
            if len(e_clean) < 2:
                continue
            if e_lower in TECH_NOT_COMPANIES:
                logger.warning(f"LLM a halluciner '{e_clean}' (c'est une tech)")
                continue
            project_indicators = ["personal project", "side project",
                                  "perso project", "academic project"]
            if any(ind in e_lower for ind in project_indicators):
                logger.warning(f"LLM a confondu projet '{e_clean}' avec entreprise")
                continue
            if "_" in e_clean or (e_clean.islower() and len(e_clean) > 5):
                logger.warning(f"Nom d'entreprise suspect : '{e_clean}'")
                continue
            cleaned_entreprises.append(e_clean)
        result["entreprises_de_stage"] = cleaned_entreprises[:10]

    # cycle
    val = data.get("cycle", "autre")
    if isinstance(val, str) and val.lower() in ["licence", "master", "ingenieur", "autre"]:
        result["cycle"] = val.lower()

    # annee_etude
    val = data.get("annee_etude")
    if isinstance(val, int) and 1 <= val <= 5:
        result["annee_etude"] = val
    elif isinstance(val, str) and val.isdigit() and 1 <= int(val) <= 5:
        result["annee_etude"] = int(val)

    # Booleens
    result["is_pfe"] = bool(data.get("is_pfe", False))
    result["has_pfe_project"] = bool(data.get("has_pfe_project", False))
    result["has_github"] = bool(data.get("has_github", False))

    # soft_skills
    val = data.get("soft_skills", [])
    if isinstance(val, list):
        result["soft_skills"] = [
            str(s).strip().lower() for s in val
            if s and isinstance(s, str) and len(str(s).strip()) >= 2
        ][:15]

    # projets_count
    val = data.get("projets_count")
    if isinstance(val, int) and 0 <= val <= 30:
        result["projets_count"] = val
    elif isinstance(val, str) and val.isdigit():
        result["projets_count"] = min(int(val), 30)

    # specialite_dominante
    val = data.get("specialite_dominante", "autre")
    allowed = ["backend", "frontend", "fullstack", "mobile",
               "data", "ai", "devops", "cybersecurite", "autre"]
    if isinstance(val, str) and val.lower() in allowed:
        result["specialite_dominante"] = val.lower()

    # Coherence : forcer is_pfe selon cycle+annee
    if result["cycle"] != "autre" and result["annee_etude"]:
        expected_pfe = (
            (result["cycle"] == "licence" and result["annee_etude"] == 3) or
            (result["cycle"] == "master" and result["annee_etude"] == 2) or
            (result["cycle"] == "ingenieur" and result["annee_etude"] in (3, 5))
        )
        if expected_pfe:
            result["is_pfe"] = True

    result["_llm_available"] = True
    return result


# =============================================================================
# FONCTION PRINCIPALE
# =============================================================================
def extract_cv_info(cv_text: str) -> Dict[str, Any]:
    """Extrait les informations structurees d'un CV via le LLM."""
    if not cv_text or len(cv_text.strip()) < 50:
        logger.warning("CV trop court pour extraction LLM")
        return DEFAULT_EXTRACTION.copy()

    truncated = cv_text[:MAX_CV_LENGTH]
    prompt = EXTRACTION_PROMPT.format(cv_text=truncated)

    try:
        parsed = llm_client.generate_json(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            temperature=LLM_TEMPERATURE,
        )
    except RuntimeError as e:
        logger.error(f"LLM extraction echouee : {e}")
        return DEFAULT_EXTRACTION.copy()
    except Exception as e:
        logger.exception(f"Erreur inattendue LLM : {e}")
        return DEFAULT_EXTRACTION.copy()

    if not parsed or not isinstance(parsed, dict):
        logger.warning("LLM a renvoye un JSON vide ou invalide")
        return DEFAULT_EXTRACTION.copy()

    cleaned = _validate_and_clean(parsed)

    logger.info(
        f"LLM extraction OK : {cleaned['nombre_stages']} stages, "
        f"cycle={cleaned['cycle']} annee={cleaned['annee_etude']}, "
        f"PFE={cleaned['is_pfe']}, entreprises={cleaned['entreprises_de_stage']}"
    )

    return cleaned