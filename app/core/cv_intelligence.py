"""
================================================================================
CV INTELLIGENCE v11.0 — Detection cycle TIMELINE-FIRST (fix bug Master/Licence)
================================================================================

CHANGEMENTS v11.0 :
- Nouvelle fonction _detect_cycle_from_timeline() : decoupe la section Formation
  en blocs avec dates, identifie la formation EN COURS, et retourne son cycle.
- _regex_detect_cycle() appelle d'abord la timeline. Si une formation en cours
  est trouvee, on l'utilise. Sinon fallback sur l'ancienne logique regex.
- Les overrides metier (IIT Sfax GLSI, Genie Informatique) ne s'appliquent
  PLUS si la timeline a deja decide (evite d'ecraser Master par Licence).
- Fix bug Ahmed : "Master Big Data (2025 - Present)" + "Licence (2022 - 2025)"
  -> cycle = master (au lieu de licence).

CHANGEMENTS v10.9 :
- Cache LLM persistant sur disque (JSON), indexe par hash MD5 du texte CV.

CHANGEMENTS v10.8 :
- Normalisation Unicode AGRESSIVE, filtre titres de projets, override GLSI.

ATTENTION : SANS LE LLM, ce systeme est en MODE DEGRADE.
================================================================================
"""

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from loguru import logger

from app.core import cv_sectionizer
from app.core import llm_cv_extractor
from app.core import triangulator


# =============================================================================
# CACHE LLM PERSISTANT (v10.9 — inchange)
# =============================================================================
_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "cache"
_CACHE_DIR.mkdir(exist_ok=True)
_CACHE_FILE = _CACHE_DIR / "llm_cv_cache.json"


def _load_cache() -> dict:
    if _CACHE_FILE.exists():
        try:
            return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Cache LLM corrompu, reinitialise : {e}")
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    try:
        _CACHE_FILE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning(f"Impossible d'ecrire le cache LLM : {e}")


def clear_cache() -> None:
    global _llm_cache
    _llm_cache = {}
    if _CACHE_FILE.exists():
        _CACHE_FILE.unlink()
    logger.info("Cache LLM vide")


_llm_cache = _load_cache()
logger.info(f"Cache LLM charge : {len(_llm_cache)} entrees depuis {_CACHE_FILE}")


# =============================================================================
# NORMALISATION UNICODE AGRESSIVE (v10.8 — inchange)
# =============================================================================
def _aggressive_normalize(text: str) -> str:
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
        "\u0307": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = unicodedata.normalize("NFKC", text)
    return text


# =============================================================================
# BLACKLIST ENTREPRISES (v10.8 — inchange)
# =============================================================================
NON_ENTREPRISE_KEYWORDS = [
    "enis", "enit", "ensi", "supcom", "isims", "iset", "isamm",
    "fseg", "iit", "napu", "esprit", "tek-up", "tek up", "ihec",
    "faculte", "faculté", "faculty", "universite", "université", "university",
    "ecole", "école", "school", "institut", "institute",
    "lycee", "lycée", "high school",
    "ieee", "google students", "google developers", "gdg", "gdsc",
    "students club", "club isims", "club isamm",
    "developer club", "aws club", "cloud club",
    "education", "diploma", "diplome", "diplôme",
    "bachelor", "master", "licence", "ingenieur", "ingénieur",
    "baccalaureat", "baccalauréat", "bac ",
    "formation", "formations", "studies", "etudes", "études",
    "scolarite", "scolarité", "parcours",
    "travail en equipe", "travail en équipe", "teamwork",
    "communication", "leadership", "autonomie",
    "gestion", "management", "organisation",
    "competences", "compétences",
    "summary", "skills", "experience", "experiences",
    "profil", "profile", "contact", "contacts",
    "languages", "langues", "interests", "interets", "intérêts",
    "projets", "projects", "certifications", "participation",
    "stage", "stages", "stage professionnel",
    "developed", "designed", "engineered", "implemented",
    "integrated", "created", "built", "managed", "led",
    "configured", "deployed", "optimized",
    "implementation", "implémentation", "developpement", "développement",
    "conception", "creation", "création", "realisation", "réalisation",
    "gestion", "amelioration", "amélioration",
    "tunisie", "tunisia", "tunisien", "tunisienne",
    "sfax", "tunis", "ariana", "sousse", "monastir",
    "france", "francais", "français",
    "linkedin", "github", "gitlab", "portfolio",
    "junior", "senior", "stagiaire", "intern",
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
    "amazon web services",
    "tunisiaflicks", "wedtect",
    "membre", "officer", "officer-", "officer–",
    "contribution", "contributions", "contributeur", "contributor",
    "captain", "capitaine", "vice captain", "vice-captain",
    "treasurer", "tresorier", "trésorier",
    "secretary", "secretaire", "secrétaire",
    "president", "président", "vice president", "vice-president",
    "leader", "team leader", "project manager",
    "volunteer", "volontaire", "benevole", "bénévole",
    "etudiante", "étudiante", "etudiant", "étudiant",
    "systemes & reseaux", "systèmes & réseaux",
    "systemes et reseaux", "systèmes et réseaux",
    "technologie & programmation", "technologie et programmation",
    "leadership & communication", "leadership et communication",
    "intelligence", "artificielle",
    "developpement web", "développement web",
    "cloud computing", "big data",
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
    "comptoir",
]

GENERIC_COMPANIES = {"google", "microsoft", "facebook", "meta",
                     "apple", "amazon", "ibm", "oracle"}


def _filter_real_entreprises(organizations: List[str], text: str) -> List[str]:
    text_normalized = _aggressive_normalize(text)
    text_lower = text_normalized.lower()
    result = []
    for org in organizations:
        if not org or not isinstance(org, str):
            continue
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


# =============================================================================
# NOUVEAU v11.0 : DETECTION CYCLE PAR TIMELINE
# =============================================================================
# Idee : decouper la section Formation en blocs (un par diplome), identifier
# pour chaque bloc son cycle ET sa periode (en cours / terminee). Le cycle
# retenu est celui de la formation EN COURS (et le plus eleve s'il y en a
# plusieurs).
#
# Fix bug Ahmed : "Master Big Data (2025-Present)" + "Licence (2022-2025)"
# -> avant : cycle="licence" (regex PRIORITE 1 matche "Licence Fondamentale")
# -> apres : cycle="master" (timeline detecte le Master en cours)
# =============================================================================

CYCLE_RANK = {
    "doctorat": 4,
    "ingenieur": 3,
    "master": 3,
    "licence": 2,
    "bts": 1,
    "bac": 0,
}

# Patterns par cycle (utilises uniquement pour la detection dans un bloc)
_CYCLE_BLOCK_PATTERNS = [
    ("doctorat",  r"\b(?:doctorat|phd|these|thèse)\b"),
    ("master",    r"\b(?:master|mastere|mastère|m1|m2|mba|msc)\b"),
    ("ingenieur", r"\b(?:ing[ée]nieur|cycle\s+ing[ée]nieur|dipl[oô]me\s+d['e]\s*ing[ée]nieur"
                  r"|[ée]l[èe]ve[\s-]ing[ée]nieur)\b"),
    ("licence",   r"\b(?:licence|bachelor|bsc|l1|l2|l3|"
                  r"diploma\s+in\s+computer|glsi)\b"),
    ("bts",       r"\b(?:bts|dut|deust)\b"),
    ("bac",       r"\b(?:baccalaur[ée]at|bac)\b"),
]

_ONGOING_KEYWORDS = [
    "present", "présent", "en cours", "actuel", "actuellement",
    "today", "now", "ongoing", "current", "à ce jour", "a ce jour",
]


def _extract_formation_section(text: str) -> str:
    """Isole la section Formation/Education du CV.

    v11.0 : utilise une regex qui matche seulement en debut de ligne (ou
    apres saut de ligne) pour eviter de matcher "Solide formation en
    informatique" dans le resume du candidat.
    """
    # Cherche un titre de section : "FORMATION", "FORMATION ACADEMIQUE",
    # "EDUCATION", "PARCOURS ACADEMIQUE", etc. -- mais SEULEMENT en debut
    # de ligne (apres \n ou en debut de texte).
    pattern = re.compile(
        r"(?:^|\n)\s*"
        r"(?:formation|éducation|education|parcours|cursus|studies)"
        r"(?:\s+(?:acad[ée]mique|scolaire|universitaire|academic|history))?"
        r"\s*:?\s*\n"
        r"(.*?)"
        r"(?=\n\s*(?:exp[ée]rience|projets?|comp[ée]tences|skills|"
        r"langues|languages|certifications?|int[ée]r[êe]ts|"
        r"interests|contact|profil|summary|references?)\b|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(text)
    if m:
        return m.group(1)
    # Fallback : ancienne regex moins stricte (au cas ou le CV n'a pas
    # de retours a la ligne propres apres le titre de section)
    fallback = re.compile(
        r"(?:formation|éducation|education)"
        r"(?:\s+(?:acad[ée]mique|scolaire|universitaire|academic|history))?"
        r"(.*?)"
        r"(?=\bexp[ée]rience|\bprojets?|\bcomp[ée]tences|\bskills|"
        r"\blangues|\blanguages|\bcertifications?|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    m2 = fallback.search(text)
    return m2.group(1) if m2 else ""


def _is_ongoing(end_str: str) -> bool:
    """Vrai si la date de fin indique 'en cours' (mot-cle ou annee future)."""
    if not end_str:
        return True
    end_lower = end_str.lower().strip()
    if any(kw in end_lower for kw in _ONGOING_KEYWORDS):
        return True
    year_match = re.search(r"\b(20\d{2})\b", end_lower)
    if year_match:
        end_year = int(year_match.group(1))
        return end_year >= datetime.now().year
    return False


def _detect_cycle_in_text_block(block: str) -> Optional[str]:
    """Detecte le cycle dans un bloc (retourne le plus eleve si plusieurs)."""
    block_lower = block.lower()
    found = []
    for cycle, pattern in _CYCLE_BLOCK_PATTERNS:
        if re.search(pattern, block_lower):
            found.append(cycle)
    if not found:
        return None
    return max(found, key=lambda c: CYCLE_RANK.get(c, 0))


def _detect_cycle_from_timeline(text: str) -> Optional[Dict[str, Any]]:
    """
    Decoupe la section Formation en blocs avec dates et retourne le cycle
    de la formation EN COURS (ou la plus recente).

    Returns None si aucun bloc avec date trouve (laisse le fallback decider).
    """
    formation = _extract_formation_section(text)
    if not formation:
        return None

    # Pattern de plage de dates : "2022 - 2025", "2025 - Present",
    # "Sept 2024 - Juin 2026", "09/2024 - 06/2026", "Septembre 2023 - Present"
    date_range_re = re.compile(
        r"((?:[A-Za-zéèêà]{3,9}\.?\s+|\d{1,2}/)?\d{4})"
        r"\s*[-–—à]\s*"
        r"((?:[A-Za-zéèêà]{3,9}\.?\s+|\d{1,2}/)?\d{4}"
        r"|present|pr[ée]sent|en\s+cours|actuel(?:lement)?|today|now|"
        r"à\s+ce\s+jour|a\s+ce\s+jour|ongoing)",
        re.IGNORECASE,
    )

    matches = list(date_range_re.finditer(formation))
    if not matches:
        return None

    blocks = []
    for i, m in enumerate(matches):
        start_pos = m.start()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(formation)
        block_text = formation[start_pos:end_pos]

        cycle = _detect_cycle_in_text_block(block_text)
        if cycle is None:
            continue

        start_year_match = re.search(r"\b(20\d{2})\b", m.group(1))
        start_year = int(start_year_match.group(1)) if start_year_match else 0
        ongoing = _is_ongoing(m.group(2))

        blocks.append({
            "cycle": cycle,
            "start_year": start_year,
            "end_str": m.group(2),
            "ongoing": ongoing,
            "snippet": block_text.strip()[:100],
        })

    if not blocks:
        return None

    # Priorite 1 : formations en cours -> prendre le cycle le plus eleve
    ongoing_blocks = [b for b in blocks if b["ongoing"]]
    if ongoing_blocks:
        best = max(
            ongoing_blocks,
            key=lambda b: (CYCLE_RANK.get(b["cycle"], 0), b["start_year"]),
        )
        logger.info(
            f"TIMELINE : formation en cours detectee -> cycle={best['cycle']} "
            f"(snippet: {best['snippet'][:60]})"
        )
        return {
            "cycle": best["cycle"],
            "source": "timeline_ongoing",
            "evidence": best["snippet"],
            "all_blocks": blocks,
        }

    # Priorite 2 : pas de formation en cours -> prendre la plus recente
    best = max(
        blocks,
        key=lambda b: (b["start_year"], CYCLE_RANK.get(b["cycle"], 0)),
    )
    logger.info(
        f"TIMELINE : aucune formation en cours, plus recente = "
        f"cycle={best['cycle']} (snippet: {best['snippet'][:60]})"
    )
    return {
        "cycle": best["cycle"],
        "source": "timeline_recent",
        "evidence": best["snippet"],
        "all_blocks": blocks,
    }


# =============================================================================
# DETECTION CYCLE — v11.0 : timeline d'abord, regex ensuite
# =============================================================================
def _regex_detect_cycle(text: str) -> Dict[str, Any]:
    if not text:
        return {"cycle": None, "annee": None, "source": "empty"}

    text_normalized = _aggressive_normalize(text)
    text_lower = text_normalized.lower()

    # ==== NOUVEAU v11.0 : TIMELINE EN PREMIER ====
    timeline = _detect_cycle_from_timeline(text_normalized)
    cycle = timeline["cycle"] if timeline else None
    source = timeline["source"] if timeline else None

    # ==== FALLBACK : ancienne logique regex (si timeline n'a rien donne) ====
    if cycle is None:
        # PRIORITE 1 : Licence explicite
        if re.search(
            r"\blicence\s+(?:en|de|appliqu[ée]e?|fondamentale?|professionnelle?)\b"
            r"|\blicence\s+(?:informatique|genie|génie|sciences?|maths?)"
            r"|\b[ée]tudiant[e]?\s+(?:en\s+)?licence\b", text_lower):
            cycle = "licence"
            source = "regex_licence"

        if cycle is None and re.search(
            r"\bcycle\s+ing[eé]nieur\b"
            r"|\bing[eé]nieur\s+(?:en\s+)?(?:informatique|logiciel|systemes?|systèmes?)\b"
            r"|\b[ée]l[èe]ve[\s-]ing[eé]nieur\b"
            r"|\b[ée]tudiant[e]?\s+ing[eé]nieur\b"
            r"|\bbac\s*\+\s*5\b"
            r"|\bdipl[ôo]me\s+d['']?ing[eé]nieur\b", text_lower):
            cycle = "ingenieur"
            source = "regex_ingenieur"

        if cycle is None and any(kw in text_lower for kw in
                                  ["master", "mastère", "mastere", " m1 ", " m2 "]):
            cycle = "master"
            source = "regex_master"

        if cycle is None:
            has_gi = bool(re.search(r"\bg[eé]nie\s+informatique\b", text_lower))
            has_gl = bool(re.search(r"\bg[eé]nie\s+logiciel\b", text_lower))
            if has_gi and not has_gl:
                cycle = "ingenieur"
                source = "regex_genie_info"
            else:
                if any(kw in text_lower for kw in [
                    "enit ", "enis ", "ensi ", "supcom",
                    "école d'ingénieurs", "ecole d'ingenieurs",
                    "école nationale d'ingénieurs", "ecole nationale d'ingenieurs",
                ]):
                    cycle = "ingenieur"
                    source = "regex_ecole_ing"

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
                source = "regex_licence_keywords"

    # ==== DETECTION ANNEE (inchange) ====
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
                    source = "regex_m_pattern"
                elif m.group(1) == "l" and cycle is None:
                    cycle = "licence"
                    source = "regex_l_pattern"
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

    return {"cycle": cycle, "annee": annee, "source": source}


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
# FONCTION PRINCIPALE — v11.0 avec timeline + cache LLM
# =============================================================================
def extract_intelligent_info(
    cv_text: str,
    organizations: List[str],
    use_llm: bool = True,
) -> Dict[str, Any]:
    """Extrait les infos critiques en combinant 3 methodes."""
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
        f"REGEX -> stages={regex_stages}, cycle={regex_cycle_info['cycle']} "
        f"(source={regex_cycle_info.get('source')}), "
        f"annee={regex_cycle_info['annee']}, pfe={regex_pfe}"
    )

    # IMPORTANT v11.0 : memoriser si la timeline a decide
    # Fix v11.1 : gerer le cas ou source est None (pas juste absent du dict)
    cycle_source = regex_cycle_info.get("source") or ""
    cycle_from_timeline = cycle_source.startswith("timeline")

    ner_stages_estimate = min(len(real_entreprises), 5) if real_entreprises else None

    # ===== APPEL LLM avec cache (v10.9) =====
    if use_llm:
        cv_hash = hashlib.md5(cv_text_normalized.encode("utf-8")).hexdigest()
        if cv_hash in _llm_cache:
            llm_result = _llm_cache[cv_hash]
            llm_available = llm_result.get("_llm_available", False)
            logger.info(f"Cache LLM HIT pour CV {cv_hash[:8]} — aucun appel API")
        else:
            logger.info(f"Cache LLM MISS pour CV {cv_hash[:8]} — appel API LLM")
            llm_result = llm_cv_extractor.extract_cv_info(cv_text_normalized)
            llm_available = llm_result.get("_llm_available", False)
            if llm_available:
                _llm_cache[cv_hash] = llm_result
                _save_cache(_llm_cache)
                logger.debug(
                    f"Resultat LLM mis en cache pour {cv_hash[:8]} "
                    f"(total cache : {len(_llm_cache)} entrees)"
                )
        if not llm_available:
            logger.warning(
                "=" * 70 + "\n"
                "ATTENTION : LE LLM N'A PAS REPONDU !\n"
                "Le systeme est en MODE DEGRADE (regex + NER uniquement).\n"
                "Verifiez qu'Ollama tourne : curl http://localhost:11434/api/tags\n"
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

    # =========================================================================
    # OVERRIDES METIER v11.0 :
    # Si la TIMELINE a deja decide, on NE force PAS.
    # Les overrides ne s'appliquent que si le cycle vient du fallback regex
    # (formation sans dates, profil ambigu, etc.)
    # =========================================================================
    if cycle_from_timeline:
        # Timeline a parle : on lui fait confiance, on force le consensus
        if cycle_consensus["value"] != regex_cycle_info["cycle"]:
            logger.info(
                f"TIMELINE OVERRIDE : consensus etait '{cycle_consensus['value']}', "
                f"timeline dit '{regex_cycle_info['cycle']}'. On suit la timeline."
            )
            cycle_consensus["value"] = regex_cycle_info["cycle"]
            cycle_consensus["confidence"] = "high"
            cycle_consensus["reason"] = (
                f"Detection par timeline ({regex_cycle_info['source']})"
            )
    else:
        # Pas de timeline : on applique les anciens overrides metier
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

        # =====================================================================
        # FIX v11.0 : Si le LLM dit un cycle PLUS ELEVE que 'licence',
        # on lui fait confiance car il a vu le contexte (timeline implicite,
        # phrase "etudiant en 1ere annee Master", etc.). L'override ne doit
        # PAS ecraser un Master par une Licence juste parce que le mot
        # "Licence Fondamentale" apparait dans l'historique du candidat.
        # =====================================================================
        llm_says_higher = (
            llm_available
            and llm_result.get("cycle") in ("master", "ingenieur")
        )

        if (explicit_licence or is_licence_glsi) and cycle_consensus["value"] != "licence":
            if llm_says_higher:
                logger.info(
                    f"OVERRIDE METIER IGNORE : 'Licence' detectee dans le texte "
                    f"mais LLM dit '{llm_result['cycle']}'. On fait confiance au LLM "
                    f"(probablement Licence dans l'historique du candidat)."
                )
            else:
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
            # Pareil pour ingenieur : si LLM dit master, on garde master
            if llm_available and llm_result.get("cycle") == "master":
                logger.info(
                    f"OVERRIDE METIER IGNORE : 'Ingenieur' detecte mais LLM dit "
                    f"'master'. On garde master."
                )
            else:
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

    text_lower_for_pfe = cv_text_normalized.lower()
    explicit_pfe_in_text = (
        re.search(r"\bpfe\b|projet\s+de\s+fin", text_lower_for_pfe) is not None
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

    # =========================================================================
    # FIX v11.1 : ENTREPRISES — priorite au LLM quand disponible
    # =========================================================================
    # Probleme : le NER spaCy detecte souvent comme "entreprises" des modules
    # de cours, des noms de technologies, ou des certifications (IBM, Microsoft
    # via "Power BI - Microsoft", "IBM Data Science Professional", etc.)
    # Le LLM avec contexte distingue beaucoup mieux les vraies entreprises de
    # stage. Si le LLM retourne au moins une entreprise, on lui fait confiance.
    # =========================================================================
    llm_entreprises = (
        llm_result.get("entreprises_de_stage", [])
        if llm_available else []
    )

    if llm_available and llm_entreprises:
        # LLM a identifie au moins une entreprise -> on lui fait confiance
        logger.info(
            f"Entreprises : priorite au LLM ({len(llm_entreprises)} entreprises) "
            f"vs NER ({len(real_entreprises)} candidats potentiellement pollues)"
        )
        entreprises_consensus = {
            "value": llm_entreprises,
            "confidence": "high",
            "sources": {"llm": llm_entreprises, "ner": real_entreprises},
            "reason": "LLM prioritaire pour entreprises (NER souvent pollue par certifs/modules)",
        }
    else:
        # Pas de LLM ou LLM n'a rien trouve -> fallback sur consensus classique
        entreprises_consensus = triangulator.consensus_list({
            "ner": real_entreprises,
            "llm": llm_entreprises if llm_available else None,
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
        "_cycle_source": regex_cycle_info.get("source"),  # NOUVEAU v11.0
    }