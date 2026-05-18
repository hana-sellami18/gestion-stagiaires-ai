"""
================================================================================
CV INTELLIGENCE v10.9 — Cache LLM persistant (optimisation Groq rate limit)
================================================================================

CHANGEMENTS v10.9 :
- Cache LLM persistant sur disque (JSON), indexe par hash MD5 du texte CV
- Reduit drastiquement les appels API : 1 appel par CV au lieu de N appels
  (N = nombre de sujets compatibles cycle/filiere)
- Garantit la reproductibilite bit-a-bit des evaluations successives
- Resout les erreurs HTTP 429 (rate limit Groq) en mode batch / gold dataset

CHANGEMENTS v10.8 :
- Normalisation Unicode AGRESSIVE (i̇ turc, İ majuscule, ᵉ exposant...)
- Filtre titres de projets (application, gestion, systeme, backend...)
- AVERTISSEMENT visible si LLM ne tourne pas (CRITIQUE pour la qualite)
- Override GLSI/Genie Logiciel renforce

ATTENTION :
SANS LE LLM, ce systeme est en MODE DEGRADE.
Verifier que Ollama tourne : `curl http://localhost:11434/api/tags`
================================================================================
"""

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, Any, Optional, List

from loguru import logger

from app.core import cv_sectionizer
from app.core import llm_cv_extractor
from app.core import triangulator


# =============================================================================
# CACHE LLM PERSISTANT (v10.9)
# =============================================================================
# Le LLM extrait les memes infos (cycle, annee, stages, PFE) pour un meme CV,
# peu importe le sujet evalue. On evite donc les appels redondants en cachant
# le resultat par hash du texte du CV.
#
# Le cache est persiste sur disque pour :
#   1. Survivre aux redemarrages du serveur
#   2. Garantir la reproductibilite des evaluations (gold dataset)
#   3. Permettre de re-generer le rapport HTML sans rappeler le LLM
#
# Localisation : <racine_projet>/cache/llm_cv_cache.json
# =============================================================================
_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "cache"
_CACHE_DIR.mkdir(exist_ok=True)
_CACHE_FILE = _CACHE_DIR / "llm_cv_cache.json"


def _load_cache() -> dict:
    """Charge le cache LLM depuis le disque."""
    if _CACHE_FILE.exists():
        try:
            return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Cache LLM corrompu, reinitialise : {e}")
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    """Sauvegarde le cache LLM sur disque."""
    try:
        _CACHE_FILE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning(f"Impossible d'ecrire le cache LLM : {e}")


def clear_cache() -> None:
    """Vide le cache LLM (utile pour les tests ou regenerer les resultats)."""
    global _llm_cache
    _llm_cache = {}
    if _CACHE_FILE.exists():
        _CACHE_FILE.unlink()
    logger.info("Cache LLM vide")


# Charge le cache au demarrage du module
_llm_cache = _load_cache()
logger.info(f"Cache LLM charge : {len(_llm_cache)} entrees depuis {_CACHE_FILE}")


# =============================================================================
# NORMALISATION UNICODE AGRESSIVE (v10.8)
# =============================================================================
# Certains CVs PDF contiennent des caracteres turcs/exotiques :
#   "APPLİCATİON" au lieu de "APPLICATION"  (I avec point U+0130)
#   "LİCENCE" au lieu de "LICENCE"
#   "appli̇cati̇on" avec combining dot U+0307
# Sans normalisation, mes regex et blacklists ne matchent pas.
# =============================================================================
def _aggressive_normalize(text: str) -> str:
    """Nettoie agressivement les caracteres Unicode exotiques."""
    if not text:
        return ""
    replacements = {
        "İ": "I", "ı": "i",
        "Ş": "S", "ş": "s",
        "Ğ": "G", "ğ": "g",
        "Ç": "C", "ç": "c",
        "ᵉ": "e", "ⁿ": "n", "ᵗ": "t", "ʳ": "r",
        "ᵈ": "d", "ᵘ": "u", "ˢ": "s",
        "’": "'", "‘": "'",
        "–": "-", "—": "-",
        "\u00a0": " ",
        "\u0307": "",  # combining dot above
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Re-normaliser via NFKD pour decomposer les autres
    text = unicodedata.normalize("NFKC", text)
    return text


# =============================================================================
# BLACKLIST ENTREPRISES (v10.8 - encore enrichie)
# =============================================================================
NON_ENTREPRISE_KEYWORDS = [
    # --- Ecoles tunisiennes ---
    "enis", "enit", "ensi", "supcom", "isims", "iset", "isamm",
    "fseg", "iit", "napu", "esprit", "tek-up", "tek up", "ihec",
    "faculte", "faculté", "faculty", "universite", "université", "university",
    "ecole", "école", "school", "institut", "institute",
    "lycee", "lycée", "high school",
    # --- Clubs etudiants ---
    "ieee", "google students", "google developers", "gdg", "gdsc",
    "students club", "club isims", "club isamm",
    "developer club", "aws club", "cloud club",
    # --- Mots academiques ---
    "education", "diploma", "diplome", "diplôme",
    "bachelor", "master", "licence", "ingenieur", "ingénieur",
    "baccalaureat", "baccalauréat", "bac ",
    "formation", "formations", "studies", "etudes", "études",
    "scolarite", "scolarité", "parcours",
    # --- Soft skills ---
    "travail en equipe", "travail en équipe", "teamwork",
    "communication", "leadership", "autonomie",
    "gestion", "management", "organisation",
    "competences", "compétences",
    # --- Sections ---
    "summary", "skills", "experience", "experiences",
    "profil", "profile", "contact", "contacts",
    "languages", "langues", "interests", "interets", "intérêts",
    "projets", "projects", "certifications", "participation",
    "stage", "stages", "stage professionnel",
    # --- Verbes anglais ---
    "developed", "designed", "engineered", "implemented",
    "integrated", "created", "built", "managed", "led",
    "configured", "deployed", "optimized",
    # --- Verbes francais courants (commencent en majuscule) ---
    "implementation", "implémentation", "developpement", "développement",
    "conception", "creation", "création", "realisation", "réalisation",
    "gestion", "amelioration", "amélioration",
    # --- Lieux ---
    "tunisie", "tunisia", "tunisien", "tunisienne",
    "sfax", "tunis", "ariana", "sousse", "monastir",
    "france", "francais", "français",
    # --- Autres ---
    "linkedin", "github", "gitlab", "portfolio",
    "junior", "senior", "stagiaire", "intern",
    # --- Technologies ---
    "jwt", "oauth", "oauth2", "mvc", "mvvm", "rest", "soap", "graphql",
    "json", "xml", "yaml", "http", "https", "tcp", "udp",
    "sql", "nosql", "orm",
    "spring", "spring boot", "django", "flask", "laravel", "symfony",
    "react", "react.js", "angular", "vue", "vue.js", "next.js",
    "node.js", "nodejs", "express", "nestjs", "nest.js",
    "mongodb", "mongoose", "mysql", "postgresql", "redis",
    "docker", "kubernetes", "aws", "azure", "gcp",
    "git", "github",
    "python", "java", "javascript", "typescript",
    "html", "css", "tailwind", "bootstrap",
    "flutter", "dart", "kotlin", "swift",
    "vite", "webpack", "babel",
    "websocket", "websockets", "socket.io",
    "passport", "passport.js", "nodemailer",
    "groq", "openai", "llama", "anthropic",
    "powerbi", "power bi", "scrumstudy",
    "intelligence artificielle", "machine learning",
    "amazon web services",  # AWS en toutes lettres
    # --- Noms de projets perso ---
    "tunisiaflicks", "wedtect",
    # --- Roles d'association ---
    "membre", "officer", "officer-", "officer–",
    "contribution", "contributions", "contributeur", "contributor",
    "captain", "capitaine", "vice captain", "vice-captain",
    "treasurer", "tresorier", "trésorier",
    "secretary", "secretaire", "secrétaire",
    "president", "président", "vice president", "vice-president",
    "leader", "team leader", "project manager",
    "volunteer", "volontaire", "benevole", "bénévole",
    "etudiante", "étudiante", "etudiant", "étudiant",
    # --- Mots de section parasites ---
    "systemes & reseaux", "systèmes & réseaux",
    "systemes et reseaux", "systèmes et réseaux",
    "technologie & programmation", "technologie et programmation",
    "leadership & communication", "leadership et communication",
    "intelligence", "artificielle",
    "developpement web", "développement web",
    "cloud computing", "big data",

    # ============= NOUVEAU v10.8 : TITRES DE PROJETS =============
    # Patterns frequents dans les CV qui ne sont PAS des entreprises
    "application", "site", "site web", "site e-commerce",
    "systeme", "système", "plateforme", "platform",
    "backend", "frontend", "fullstack",
    "mobile app", "web app", "desktop app",
    "jeu", "game", "runner",
    "generateur", "générateur",
    "tableau de bord", "dashboard",
    "service apres-vente", "service après-vente", "sav ",
    "e-commerce", "ecommerce",
    "chatbot", "chat bot",
    "portfolio", "cv professionnel",
    "labyrinthe", "challenge", "competition",
    "afro tech", "afrotech",
    "comptoir",  # "Comptoir Hammemi" est une entreprise mais souvent confondu
]

GENERIC_COMPANIES = {"google", "microsoft", "facebook", "meta",
                     "apple", "amazon", "ibm", "oracle"}


def _filter_real_entreprises(organizations: List[str], text: str) -> List[str]:
    """Filtre rigoureusement les organisations du NER."""
    text_normalized = _aggressive_normalize(text)
    text_lower = text_normalized.lower()
    result = []
    for org in organizations:
        if not org or not isinstance(org, str):
            continue

        # IMPORTANT v10.8 : normaliser AUSSI le nom de l'organisation
        org_normalized = _aggressive_normalize(org)
        org_clean = org_normalized.strip()
        org_lower = org_clean.lower()

        if len(org_clean) < 3 or len(org_clean) > 50:
            continue
        if any(kw in org_lower for kw in NON_ENTREPRISE_KEYWORDS):
            continue
        if org_lower in {"jwt", "css", "html", "php", "sql", "rest", "mvc",
                         "git", "aws", "vue", "java", "dart", "ssh"}:
            continue
        if "\n" in org_clean:
            continue
        if not org_clean[0].isupper():
            continue
        if len(org_clean.split()) > 5:
            continue
        if org_lower in GENERIC_COMPANIES:
            club_contexts = [f"{org_lower} students club", f"{org_lower} club",
                             f"club {org_lower}", f"{org_lower} students",
                             f"{org_lower} developer"]
            if any(ctx in text_lower for ctx in club_contexts):
                continue
        if not any(c.isalpha() for c in org_clean):
            continue
        if len(org_clean) <= 5 and org_clean.isupper():
            continue
        if "&" in org_clean and len(org_clean) < 30:
            continue
        if re.match(r"^[A-Z][a-zé]+[\-–.,;:]", org_clean):
            continue

        # NOUVEAU v10.8 : Si tout en MAJUSCULES, c'est probablement
        # un titre de section ou de projet (et pas un nom d'entreprise)
        if org_clean.isupper() and len(org_clean) > 5:
            continue

        result.append(org_clean)

    seen = set()
    deduplicated = []
    for org in result:
        key = org.lower()
        if key not in seen:
            seen.add(key)
            deduplicated.append(org)
    return deduplicated


def _regex_count_stages(text: str, real_entreprises: List[str]) -> Optional[int]:
    if not text:
        return None
    text = _aggressive_normalize(text)
    date_pattern = re.compile(
        r"(?:\d{1,2}[/\-]\d{4}"
        r"|(?:janv|févr|fevr|mars|avr|mai|juin|juil|août|aout|sept|septembre|"
        r"octobre|novembre|décembre|january|february|march|april|june|july|"
        r"august|september|october|november|december|jan|feb|mar|apr|jun|jul|"
        r"aug|sep|oct|nov|dec)[a-zé.]*\s*\d{4}"
        r"|\d{4}\s*[-–à]\s*\d{4})", flags=re.IGNORECASE)
    strong_stage_pattern = re.compile(
        r"\b(?:stage|stagiaire|internship|intern|pfa|pfe)\b"
        r"|projet\s+de\s+fin\s+d['e]'?[ée]tudes?", flags=re.IGNORECASE)
    numbered_pattern = re.compile(
        r"(?:^|\n)\s*(\d+)\.\s+[A-Z][A-Za-zÀ-ÿ\-&\s]{2,40}", flags=re.MULTILINE)

    blocks = re.split(r"\n\s*\n", text)
    count = 0
    for block in blocks:
        block_lower = block.lower()
        if not date_pattern.search(block):
            continue
        if strong_stage_pattern.search(block):
            count += 1
            continue
        for org in real_entreprises:
            if len(org) >= 3 and org.lower() in block_lower:
                count += 1
                break

    numbered_matches = numbered_pattern.findall(text)
    if numbered_matches and count < len(numbered_matches):
        count = max(count, min(len(numbered_matches), 6))
    return min(count, 10)


def _estimate_year_from_dates(text: str, cycle: Optional[str]) -> Optional[int]:
    if not text or not cycle:
        return None
    from datetime import datetime
    current_year = datetime.now().year
    patterns = [
        r"(?:sep|sept|septembre|aug|august|aout|oct|jan|fev|feb|mar)\w*\s+(\d{4})\s*[-–]\s*"
        r"(?:juin|june|jun|juil|jul|sep|sept|oct|aug)\w*\s+(\d{4})",
        r"\b(\d{4})\s*[-–_]\s*(\d{4})\b",
    ]
    for pattern in patterns:
        for start_str, end_str in re.findall(pattern, text, flags=re.IGNORECASE):
            try:
                start, end = int(start_str), int(end_str)
                if not (2015 <= start <= 2035 and 2015 <= end <= 2035):
                    continue
                if end <= start:
                    continue
                duration = end - start
                expected_durations = {"licence": [3], "master": [2], "ingenieur": [3, 5]}
                if duration in expected_durations.get(cycle, []):
                    if current_year <= end:
                        year_in_cycle = current_year - start + 1
                        if 1 <= year_in_cycle <= duration:
                            return year_in_cycle
            except (ValueError, TypeError):
                continue
    return None


def _regex_detect_cycle(text: str) -> Dict[str, Any]:
    if not text:
        return {"cycle": None, "annee": None}

    # v10.8 : normaliser AGRESSIVEMENT avant matching
    text_normalized = _aggressive_normalize(text)
    text_lower = text_normalized.lower()
    cycle = None

    # PRIORITE 1 : Licence explicite
    if re.search(
        r"\blicence\s+(?:en|de|appliqu[ée]e?|fondamentale?|professionnelle?)\b"
        r"|\blicence\s+(?:informatique|genie|génie|sciences?|maths?)"
        r"|\b[ée]tudiant[e]?\s+(?:en\s+)?licence\b", text_lower):
        cycle = "licence"

    if cycle is None and re.search(
        r"\bcycle\s+ing[eé]nieur\b"
        r"|\bing[eé]nieur\s+(?:en\s+)?(?:informatique|logiciel|systemes?|systèmes?)\b"
        r"|\b[ée]l[èe]ve[\s-]ing[eé]nieur\b"
        r"|\b[ée]tudiant[e]?\s+ing[eé]nieur\b"
        r"|\bbac\s*\+\s*5\b"
        r"|\bdipl[ôo]me\s+d['']?ing[eé]nieur\b", text_lower):
        cycle = "ingenieur"

    if cycle is None and any(kw in text_lower for kw in
                              ["master", "mastère", "mastere", " m1 ", " m2 "]):
        cycle = "master"

    if cycle is None:
        has_gi = bool(re.search(r"\bg[eé]nie\s+informatique\b", text_lower))
        has_gl = bool(re.search(r"\bg[eé]nie\s+logiciel\b", text_lower))
        if has_gi and not has_gl:
            cycle = "ingenieur"
        else:
            if any(kw in text_lower for kw in [
                "enit ", "enis ", "ensi ", "supcom",
                "école d'ingénieurs", "ecole d'ingenieurs",
                "école nationale d'ingénieurs", "ecole nationale d'ingenieurs",
            ]):
                cycle = "ingenieur"

    if cycle is None:
        if any(kw in text_lower for kw in [
            "licence", "bachelor", "bac+3", "bac+2",
            "génie logiciel", "geni logiciel", "genie logiciel",
            "systèmes d'information", "systemes d'information", "glsi",
            "iset", "dut", "bts", "iit ", "isims",
            "diploma in computer", "diploma in computer science",
            "diplôme en informatique", "diplome en informatique",
            "bachelor's degree", "bachelor degree",
        ]):
            cycle = "licence"

    annee = None
    m = re.search(r"(\d)\s*(?:ème|eme|er|ère|nd|rd|th|e|ᵉ)?\s*ann[ée]e", text_lower)
    if m:
        try:
            annee = int(m.group(1))
        except ValueError:
            pass
    if annee is None:
        m = re.search(r"(\d)\s*(?:ème|eme|er|ère|e|ᵉ)?\s*(?:g[eé]ni[e]?|cycle)", text_lower)
        if m:
            try:
                annee = int(m.group(1))
            except ValueError:
                pass
    if annee is None:
        m = re.search(r"\b([lm])(\d)\b", text_lower)
        if m:
            try:
                annee = int(m.group(2))
                if m.group(1) == "m" and cycle != "master":
                    cycle = "master"
                elif m.group(1) == "l" and cycle is None:
                    cycle = "licence"
            except ValueError:
                pass
    if annee is None:
        for kw, val in {"first year": 1, "1st year": 1, "second year": 2,
                        "2nd year": 2, "third year": 3, "3rd year": 3,
                        "fourth year": 4, "4th year": 4, "fifth year": 5,
                        "5th year": 5, "final-year": 3, "final year": 3,
                        "graduating": 3}.items():
            if kw in text_lower:
                annee = val
                break
    if annee is None and cycle:
        annee = _estimate_year_from_dates(text_normalized, cycle)
        if annee:
            logger.info(f"Annee estimee depuis les dates : {annee}")

    return {"cycle": cycle, "annee": annee}


def _regex_detect_pfe(text: str, cycle: Optional[str], annee: Optional[int]) -> bool:
    if cycle and annee:
        if ((cycle == "licence" and annee == 3) or
            (cycle == "master" and annee == 2) or
            (cycle == "ingenieur" and annee in (3, 5))):
            return True
    if text:
        text_norm = _aggressive_normalize(text).lower()
        if re.search(
            r"\b(?:pfe|projet\s+de\s+fin\s+d['e]'?[ée]tudes?"
            r"|end[\s-]of[\s-]studies?[\s-]project)\b", text_norm):
            return True
    return False


# =============================================================================
# FONCTION PRINCIPALE — v10.9 avec cache LLM persistant
# =============================================================================
def extract_intelligent_info(
    cv_text: str,
    organizations: List[str],
    use_llm: bool = True,
) -> Dict[str, Any]:
    """Extrait les infos critiques en combinant 3 methodes."""
    # v10.8 : normaliser le texte des le debut
    cv_text_normalized = _aggressive_normalize(cv_text)

    real_entreprises = _filter_real_entreprises(organizations, cv_text_normalized)
    logger.info(
        f"Entreprises filtrees : {len(organizations)} brutes "
        f"-> {len(real_entreprises)} reelles : {real_entreprises[:5]}"
    )

    sections = cv_sectionizer.split_into_sections(cv_text_normalized)
    logger.info(f"Sections detectees : {list(sections.keys())}")

    experience_text = cv_sectionizer.get_combined_text(
        sections, ["experience", "_header"]
    ) or cv_text_normalized

    regex_stages = _regex_count_stages(experience_text, real_entreprises)
    regex_cycle_info = _regex_detect_cycle(cv_text_normalized)
    regex_pfe = _regex_detect_pfe(
        cv_text_normalized,
        regex_cycle_info["cycle"],
        regex_cycle_info["annee"]
    )

    logger.debug(
        f"REGEX -> stages={regex_stages}, cycle={regex_cycle_info['cycle']}, "
        f"annee={regex_cycle_info['annee']}, pfe={regex_pfe}"
    )

    ner_stages_estimate = min(len(real_entreprises), 5) if real_entreprises else None

    # ===========================================================================
    # APPEL LLM avec CACHE par hash du CV (v10.9)
    # ===========================================================================
    # Le LLM extrait des infos invariantes par rapport au sujet evalue.
    # On cache donc le resultat par hash MD5 du texte normalise du CV.
    # ===========================================================================
    if use_llm:
        cv_hash = hashlib.md5(cv_text_normalized.encode("utf-8")).hexdigest()

        if cv_hash in _llm_cache:
            llm_result = _llm_cache[cv_hash]
            llm_available = llm_result.get("_llm_available", False)
            logger.info(
                f"Cache LLM HIT pour CV {cv_hash[:8]} — aucun appel API"
            )
        else:
            logger.info(f"Cache LLM MISS pour CV {cv_hash[:8]} — appel API LLM")
            llm_result = llm_cv_extractor.extract_cv_info(cv_text_normalized)
            llm_available = llm_result.get("_llm_available", False)

            # On ne met en cache que les resultats valides
            # (sinon on garderait un "echec" et on ne reessaierait jamais)
            if llm_available:
                _llm_cache[cv_hash] = llm_result
                _save_cache(_llm_cache)
                logger.debug(
                    f"Resultat LLM mis en cache pour {cv_hash[:8]} "
                    f"(total cache : {len(_llm_cache)} entrees)"
                )

        # CRITIQUE : avertir l'utilisateur si LLM ne tourne pas
        if not llm_available:
            logger.warning(
                "=" * 70 + "\n"
                "ATTENTION : LE LLM N'A PAS REPONDU !\n"
                "Le systeme est en MODE DEGRADE (regex + NER uniquement).\n"
                "Verifiez qu'Ollama tourne : curl http://localhost:11434/api/tags\n"
                "Et que le modele est installe : ollama list\n"
                + "=" * 70
            )
    else:
        llm_result = llm_cv_extractor.DEFAULT_EXTRACTION.copy()
        llm_available = False

    logger.debug(
        f"LLM -> stages={llm_result['nombre_stages']}, "
        f"cycle={llm_result['cycle']}, annee={llm_result['annee_etude']}, "
        f"pfe={llm_result['is_pfe']}"
    )

    # ===== Triangulation =====
    ner_for_voting = ner_stages_estimate
    if (regex_stages is not None and regex_stages == 0
            and llm_available
            and llm_result["nombre_stages"] is not None
            and llm_result["nombre_stages"] > 0):
        logger.info(
            f"Regex=0 et LLM={llm_result['nombre_stages']}. "
            f"On ignore le NER (={ner_stages_estimate}) pour eviter le bruit."
        )
        ner_for_voting = None

    stages_consensus = triangulator.consensus_numeric(
        values={
            "regex": regex_stages,
            "ner": ner_for_voting,
            "llm": llm_result["nombre_stages"] if llm_available else None,
        },
        tolerance=1,
    )

    cycle_consensus = triangulator.consensus_categorical({
        "regex": regex_cycle_info["cycle"],
        "llm": llm_result["cycle"] if llm_available else None,
    })

    # ===========================================================================
    # OVERRIDES METIER v10.7/10.8
    # ===========================================================================
    text_lower_for_override = cv_text_normalized.lower()

    explicit_licence = bool(re.search(
        r"\blicence\s+(?:en|de|appliqu[ée]e?|fondamentale?|professionnelle?)\b"
        r"|\blicence\s+(?:informatique|genie|génie|sciences?|maths?)"
        r"|\b[ée]tudiant[e]?\s+(?:en\s+)?licence\b",
        text_lower_for_override,
    ))

    has_genie_logiciel = bool(re.search(
        r"\bg[eé]nie\s+logiciel\b", text_lower_for_override
    ))
    has_genie_informatique = bool(re.search(
        r"\bg[eé]nie\s+informatique\b", text_lower_for_override
    ))
    is_licence_glsi = has_genie_logiciel and not has_genie_informatique

    explicit_ingenieur = bool(re.search(
        r"\bcycle\s+ing[eé]nieur\b"
        r"|\bing[eé]nieur\s+(?:en\s+)?(?:informatique|logiciel|systemes?|systèmes?)\b"
        r"|\b[ée]l[èe]ve[\s-]ing[eé]nieur\b"
        r"|\b[ée]tudiant[e]?\s+ing[eé]nieur\b",
        text_lower_for_override,
    ))
    is_pure_ingenieur = has_genie_informatique and not has_genie_logiciel

    if (explicit_licence or is_licence_glsi) and cycle_consensus["value"] != "licence":
        reason = ("'Licence' explicite" if explicit_licence
                  else "'Genie Logiciel' (specialite Licence en Tunisie)")
        logger.info(
            f"OVERRIDE METIER : {reason}. "
            f"Cycle force de '{cycle_consensus['value']}' a 'licence'"
        )
        cycle_consensus["value"] = "licence"
        cycle_consensus["confidence"] = "high"
        cycle_consensus["reason"] = f"Override metier : {reason}"

    elif (explicit_ingenieur or is_pure_ingenieur) and cycle_consensus["value"] != "ingenieur":
        reason = ("'Cycle ingenieur' explicite" if explicit_ingenieur
                  else "'Genie Informatique' seul (specialite Ingenieur)")
        logger.info(
            f"OVERRIDE METIER : {reason}. "
            f"Cycle force de '{cycle_consensus['value']}' a 'ingenieur'"
        )
        cycle_consensus["value"] = "ingenieur"
        cycle_consensus["confidence"] = "high"
        cycle_consensus["reason"] = f"Override metier : {reason}"

    annee_consensus = triangulator.consensus_numeric({
        "regex": regex_cycle_info["annee"],
        "llm": llm_result["annee_etude"] if llm_available else None,
    })

    explicit_pfe_in_text = (
        re.search(r"\bpfe\b|projet\s+de\s+fin", text_lower_for_override) is not None
    )

    pfe_consensus = triangulator.consensus_boolean({
        "regex": regex_pfe,
        "llm": llm_result["is_pfe"] if llm_available else None,
    })

    if explicit_pfe_in_text and regex_pfe:
        pfe_consensus["value"] = True
        pfe_consensus["confidence"] = triangulator.CONFIDENCE_HIGH
        pfe_consensus["reason"] = "Mot 'PFE' explicite dans le CV"

    if cycle_consensus["value"] and annee_consensus["value"]:
        c = cycle_consensus["value"]
        a = annee_consensus["value"]
        if ((c == "licence" and a == 3) or
            (c == "master" and a == 2) or
            (c == "ingenieur" and a in (3, 5))):
            pfe_consensus["value"] = True
            if pfe_consensus["confidence"] != triangulator.CONFIDENCE_HIGH:
                pfe_consensus["confidence"] = triangulator.CONFIDENCE_MEDIUM

    entreprises_consensus = triangulator.consensus_list({
        "ner": real_entreprises,
        "llm": llm_result["entreprises_de_stage"] if llm_available else None,
    })

    soft_skills_consensus = triangulator.consensus_list({
        "llm": llm_result["soft_skills"] if llm_available else None,
    })

    overall = triangulator.overall_confidence(
        stages_consensus, cycle_consensus, annee_consensus, pfe_consensus
    )

    return {
        "sections": sections,
        "stages": stages_consensus,
        "cycle": cycle_consensus,
        "annee": annee_consensus,
        "is_pfe": pfe_consensus,
        "entreprises": entreprises_consensus,
        "soft_skills": soft_skills_consensus,
        "overall_confidence": overall,
        "_llm_used": llm_available,
        "_raw_llm_result": llm_result if llm_available else None,
        "_real_entreprises_count": len(real_entreprises),
    }