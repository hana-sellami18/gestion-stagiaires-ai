"""
Orchestrateur principal : PDF → JSON structuré.
Combine PDFExtractor + SkillsExtractor + NERExtractor + Anonymizer.

v11.0 : detect_cycle() utilise la timeline (formation EN COURS) au lieu
        de compter les occurrences. Fix bug Ahmed (Master en cours classe
        en Licence parce que "Licence Fondamentale" apparait dans son
        historique 2022-2025).
"""
import re
from datetime import datetime
from pathlib import Path

from loguru import logger

from app.core.pdf_extractor import pdf_extractor
from app.core.skills_extractor import skills_extractor
from app.core.ner_extractor import ner_extractor
from app.core.anonymizer import anonymizer


# ---------------------------------------------------------------------------
# Détection cycle académique — v11.0 timeline-first
# ---------------------------------------------------------------------------

CYCLE_ORDER = {"licence": 1, "ingenieur": 2, "master": 3}
CYCLE_RANK = {"doctorat": 4, "ingenieur": 3, "master": 3, "licence": 2,
              "bts": 1, "bac": 0}

# Patterns pour detecter le cycle DANS UN BLOC formation (avec date)
_CYCLE_BLOCK_PATTERNS = [
    ("doctorat",  r"\b(?:doctorat|phd|these|thèse)\b"),
    ("master",    r"\b(?:master|mastere|mastère|m1|m2|mba|msc)\b"),
    ("ingenieur", r"\b(?:cycle\s+ing[ée]nieur|dipl[oô]me\s+d['e]\s*ing[ée]nieur"
                  r"|[ée]l[èe]ve[\s-]ing[ée]nieur|ing[ée]nieur\s+en\s+(?:informatique|logiciel))\b"),
    ("licence",   r"\b(?:licence|bachelor|bsc|l1|l2|l3|"
                  r"diploma\s+in\s+computer|glsi)\b"),
    ("bts",       r"\b(?:bts|dut|deust)\b"),
    ("bac",       r"\b(?:baccalaur[ée]at|bac)\b"),
]

_ONGOING_KEYWORDS = [
    "present", "présent", "en cours", "actuel", "actuellement",
    "today", "now", "ongoing", "current", "à ce jour", "a ce jour",
]

# Fallback patterns (utilises seulement si la timeline ne trouve rien)
CYCLE_PATTERNS = [
    (r"\bmaster\s*\d?\b", "master"),
    (r"\bm\s*[12]\b", "master"),
    (r"\bbig\s*data\b.{0,30}\bmaster\b", "master"),
    (r"\bmaster\b.{0,30}\b(big\s*data|intelligence|data\s*science|ia|bi)\b", "master"),
    (r"\bcycle\s+ing[eé]nieur\b", "ingenieur"),
    (r"\bing[eé]nieur\b.{0,20}\b(informatique|logiciel|syst[eè]mes)\b", "ingenieur"),
    (r"\b[eé]tudiant[e]?\s+ing[eé]nieur\b", "ingenieur"),
    (r"\b[eé]cole\s+(nationale|sup[eé]rieure|d'ing[eé]nieurs)\b", "ingenieur"),
    (r"\b(esprit|enis|insat|polytechnique)\b", "ingenieur"),
    (r"\blicence\b", "licence"),
    (r"\bl[23]\b", "licence"),
    (r"\b(iset|iit|fseg|fst|isims)\b", "licence"),
    (r"\b[eé]tudiant[e]?\s+en\s+\d[eè][mr][e]?\s+ann[eé]e\b", "licence"),
]

FILIERE_PATTERNS = [
    (r"\binformatique\b", "Informatique"),
    (r"\bg[eé]nie\s+logiciel\b", "Informatique"),
    (r"\bglsi\b", "Informatique"),
    (r"\bd[eé]veloppement\s+(des\s+syst[eè]mes|logiciel|web)\b", "Informatique"),
    (r"\bsyst[eè]mes?\s+d.information\b", "Informatique"),
    (r"\bcybers[eé]curit[eé]\b", "Informatique"),
    (r"\bsciences?\s+de\s+l.informatique\b", "Informatique"),
    (r"\bbig\s*data\b", "Informatique"),
    (r"\bintelligence\s+artificielle\b", "Informatique"),
    (r"\breseaux?\b", "Informatique"),
]


def _extract_formation_section(text: str) -> str:
    """Isole la section Formation/Education du CV."""
    pattern = re.compile(
        r"(formation|éducation|education|parcours\s+acad[ée]mique|studies?|"
        r"academic\s+background|cursus)"
        r"(.*?)"
        r"(?=\bexp[ée]rience|\bprojets?|\bcomp[ée]tences|\bskills|"
        r"\blangues|\blanguages|\bcertifications?|\bint[ée]r[êe]ts|"
        r"\binterests|\bcontact|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(2) if m else ""


def _is_ongoing(end_str: str) -> bool:
    """Vrai si la date de fin indique 'en cours' (mot-cle ou annee future)."""
    if not end_str:
        return True
    end_lower = end_str.lower().strip()
    if any(kw in end_lower for kw in _ONGOING_KEYWORDS):
        return True
    year_match = re.search(r"\b(20\d{2})\b", end_lower)
    if year_match:
        return int(year_match.group(1)) >= datetime.now().year
    return False


def _detect_cycle_in_block(block: str) -> str | None:
    """Detecte le cycle dans un bloc (retourne le plus eleve si plusieurs)."""
    block_lower = block.lower()
    found = []
    for cycle, pattern in _CYCLE_BLOCK_PATTERNS:
        if re.search(pattern, block_lower):
            found.append(cycle)
    if not found:
        return None
    return max(found, key=lambda c: CYCLE_RANK.get(c, 0))


def _detect_cycle_from_timeline(text: str) -> str | None:
    """
    Decoupe la section Formation en blocs avec dates et retourne le cycle
    de la formation EN COURS (ou la plus recente).

    Returns None si aucun bloc avec date trouve.
    """
    formation = _extract_formation_section(text)
    if not formation:
        # Fallback : essayer sur le texte complet
        formation = text

    date_range_re = re.compile(
        r"((?:[A-Za-zéèêà]{3,9}\.?\s+|\d{1,2}/)?\d{4})"
        r"\s*[-–—à|]\s*"
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

        cycle = _detect_cycle_in_block(block_text)
        if cycle is None:
            continue

        start_year_match = re.search(r"\b(20\d{2})\b", m.group(1))
        start_year = int(start_year_match.group(1)) if start_year_match else 0
        ongoing = _is_ongoing(m.group(2))

        blocks.append({
            "cycle": cycle,
            "start_year": start_year,
            "ongoing": ongoing,
            "snippet": block_text.strip()[:80],
        })

    if not blocks:
        return None

    # Mapper "ingenieur"/"bts"/"bac" vers les 3 cycles supportes en aval
    def _normalize_cycle(c):
        if c in ("doctorat", "master"):
            return "master"
        if c == "ingenieur":
            return "ingenieur"
        # bts, bac, licence -> licence
        return "licence"

    # Priorite 1 : formations en cours
    ongoing_blocks = [b for b in blocks if b["ongoing"]]
    if ongoing_blocks:
        best = max(
            ongoing_blocks,
            key=lambda b: (CYCLE_RANK.get(b["cycle"], 0), b["start_year"]),
        )
        normalized = _normalize_cycle(best["cycle"])
        logger.info(
            f"TIMELINE : formation en cours -> cycle={normalized} "
            f"(bloc: {best['snippet'][:60]})"
        )
        return normalized

    # Priorite 2 : pas de formation en cours -> la plus recente
    best = max(
        blocks,
        key=lambda b: (b["start_year"], CYCLE_RANK.get(b["cycle"], 0)),
    )
    normalized = _normalize_cycle(best["cycle"])
    logger.info(
        f"TIMELINE : formation la plus recente -> cycle={normalized} "
        f"(bloc: {best['snippet'][:60]})"
    )
    return normalized


def detect_cycle(text: str) -> str:
    """
    Détecte le cycle académique depuis le texte du CV.

    v11.0 : essaie d'abord la timeline (formation en cours), puis fallback
    sur l'ancienne logique de comptage si la timeline ne trouve rien.

    Retourne 'licence', 'ingenieur' ou 'master'.
    """
    # ===== TIMELINE D'ABORD =====
    timeline_cycle = _detect_cycle_from_timeline(text)
    if timeline_cycle:
        return timeline_cycle

    # ===== FALLBACK : ancienne logique de comptage =====
    logger.info("Timeline n'a rien trouve, fallback sur le comptage de patterns")
    text_lower = text.lower()
    detected = {}

    for pattern, cycle in CYCLE_PATTERNS:
        if re.search(pattern, text_lower):
            detected[cycle] = detected.get(cycle, 0) + 1

    if not detected:
        return "licence"

    # Priorité au cycle le plus élevé détecté
    best = max(detected, key=lambda c: (CYCLE_ORDER.get(c, 0), detected[c]))
    return best


def detect_filiere(text: str) -> str:
    """
    Détecte la filière depuis le texte du CV.
    Retourne 'Informatique' ou '' si non détectée.
    """
    text_lower = text.lower()
    for pattern, filiere in FILIERE_PATTERNS:
        if re.search(pattern, text_lower):
            return filiere
    return "Informatique"  # défaut pour ce contexte


# ---------------------------------------------------------------------------
# CVParser
# ---------------------------------------------------------------------------

class CVParser:
    """Pipeline complet d'analyse de CV."""

    def parse(self, pdf_source: bytes | str | Path) -> dict:
        """
        Analyse complète d'un CV.

        :param pdf_source: bytes du PDF ou chemin
        :return: dict structuré complet avec cycle et filière
        """
        # 1) Extraction texte brut
        extraction = pdf_extractor.extract(pdf_source)
        text = extraction["text"]

        if not text.strip():
            logger.warning("Aucun texte extrait du PDF")
            return {
                "extraction": extraction,
                "skills": {"found_skills": [], "by_category": {}, "total": 0},
                "ner": {"organizations": [], "education_lines": [], "years": []},
                "cycle": "licence",
                "filiere": "Informatique",
                "warning": "PDF vide ou illisible",
            }

        # 2) Détection cycle et filière AVANT anonymisation (le texte original
        #    contient les noms d'écoles utiles pour détecter le cycle)
        cycle = detect_cycle(text)
        filiere = detect_filiere(text)
        logger.info(f"Cycle détecté : {cycle} | Filière : {filiere}")

        # 3) Anonymisation avant analyse (conformité AI Act + RGPD)
        text_anonymized = anonymizer.anonymize(text)
        logger.info("Texte anonymisé avant analyse (AI Act art. 10)")

        # 4) Extraction compétences sur texte anonymisé
        skills = skills_extractor.extract(
            text_anonymized, filtered_categories=["informatique"]
        )

        # 5) Extraction entités sur texte anonymisé
        ner = ner_extractor.extract(text_anonymized)

        logger.info(
            f"CV parsé : {skills['total']} compétences, "
            f"{len(ner['education_lines'])} lignes formation, "
            f"{len(ner['years'])} années détectées"
        )

        return {
            "extraction": {
                "method": extraction["method"],
                "num_pages": extraction["num_pages"],
                "char_count": extraction["char_count"],
            },
            "skills": skills,
            "ner": ner,
            # Cycle et filière détectés (utilisés pour le filtrage des sujets)
            "cycle": cycle,
            "filiere": filiere,
            # Preview du texte anonymisé (pas l'original)
            "raw_text_preview": text_anonymized,
            # Indicateur de conformité
            "anonymized": True,
        }


# Singleton
cv_parser = CVParser()