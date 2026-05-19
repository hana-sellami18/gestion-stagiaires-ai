"""
Orchestrateur principal : PDF → JSON structuré.
Combine PDFExtractor + SkillsExtractor + NERExtractor + Anonymizer.
"""
import re
from pathlib import Path

from loguru import logger

from app.core.pdf_extractor import pdf_extractor
from app.core.skills_extractor import skills_extractor
from app.core.ner_extractor import ner_extractor
from app.core.anonymizer import anonymizer


# ---------------------------------------------------------------------------
# Détection cycle académique
# ---------------------------------------------------------------------------

CYCLE_PATTERNS = [
    # Master (priorité haute)
    (r"\bmaster\s*\d?\b", "master"),
    (r"\bm\s*[12]\b", "master"),
    (r"\bbig\s*data\b.{0,30}\bmaster\b", "master"),
    (r"\bmaster\b.{0,30}\b(big\s*data|intelligence|data\s*science|ia|bi)\b", "master"),

    # Ingénieur
    (r"\bcycle\s+ing[eé]nieur\b", "ingenieur"),
    (r"\bing[eé]nieur\b.{0,20}\b(informatique|logiciel|syst[eè]mes)\b", "ingenieur"),
    (r"\b[eé]tudiant[e]?\s+ing[eé]nieur\b", "ingenieur"),
    (r"\b[eé]cole\s+(nationale|sup[eé]rieure|d'ing[eé]nieurs)\b", "ingenieur"),
    (r"\b(esprit|enis|insat|polytechnique)\b", "ingenieur"),

    # Licence (priorité basse)
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

CYCLE_ORDER = {"licence": 1, "ingenieur": 2, "master": 3}


def detect_cycle(text: str) -> str:
    """
    Détecte le cycle académique depuis le texte du CV.
    Retourne 'licence', 'ingénieur' ou 'master'.
    En cas de doute, retourne 'licence' (le plus conservateur).
    """
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