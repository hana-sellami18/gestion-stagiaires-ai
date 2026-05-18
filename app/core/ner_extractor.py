"""
Extracteur d'entités nommées via spaCy : formations, organisations, dates.
"""
import re
from typing import Optional

import spacy
from loguru import logger

from app.config import settings


class NERExtractor:
    """Extrait formations, organisations, dates depuis un CV."""

    # Mots-clés pour détecter une ligne de formation
    EDUCATION_KEYWORDS = [
        "licence", "master", "doctorat", "phd", "ingénieur", "ingénieure",
        "bachelor", "bac+", "diplôme", "diploma", "btp", "bts", "dut",
        "ensi", "enit", "iset", "université", "university", "école",
        "school", "institut", "faculté", "esprit", "esp ", "supcom"
    ]

    # Pattern pour les années (1990-2099)
    YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")

    def __init__(self):
        logger.info(f"Chargement spaCy : {settings.spacy_model}")
        try:
            self.nlp = spacy.load(settings.spacy_model)
        except OSError:
            logger.error(
                f"Modèle spaCy '{settings.spacy_model}' introuvable. "
                f"Lance : python -m spacy download {settings.spacy_model}"
            )
            raise

    def extract(self, text: str) -> dict:
        """
        Extrait les entités structurées du CV.

        :return: dict avec organizations, education_lines, years, full_entities
        """
        if not text:
            return {"organizations": [], "education_lines": [], "years": [], "entities": []}

        # spaCy a une limite par défaut → on découpe si CV très long
        doc = self.nlp(text[:1_000_000])

        organizations = self._extract_organizations(doc)
        years = self._extract_years(text)
        education_lines = self._extract_education_lines(text)

        # Vue brute (utile pour debug/extension)
        all_entities = [
            {"text": ent.text, "label": ent.label_}
            for ent in doc.ents
            if ent.label_ in ("ORG", "LOC", "PER", "MISC", "DATE")
        ]

        return {
            "organizations": organizations,
            "education_lines": education_lines,
            "years": years,
            "entities": all_entities[:50],  # cap pour éviter explosion
        }

    def _extract_organizations(self, doc) -> list[str]:
        """Récupère les ORG détectées par spaCy, dédoublonnées."""
        orgs = set()
        for ent in doc.ents:
            if ent.label_ == "ORG" and len(ent.text.strip()) > 2:
                orgs.add(ent.text.strip())
        return sorted(orgs)

    def _extract_years(self, text: str) -> list[int]:
        """Extrait les années plausibles (1990-2030) du texte."""
        all_years = {int(m.group()) for m in self.YEAR_PATTERN.finditer(text)}
        # Filtre : années réalistes pour un CV d'étudiant
        plausible = {y for y in all_years if 2000 <= y <= 2030}
        return sorted(plausible)

    def _extract_education_lines(self, text: str) -> list[str]:
        """Repère les lignes contenant un mot-clé de formation."""
        lines = text.split("\n")
        education = []
        for line in lines:
            line_lower = line.lower().strip()
            if not line_lower or len(line_lower) < 5:
                continue
            if any(kw in line_lower for kw in self.EDUCATION_KEYWORDS):
                education.append(line.strip())
        return education[:10]  # max 10 lignes pertinentes


# Singleton
ner_extractor = NERExtractor()