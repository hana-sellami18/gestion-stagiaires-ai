"""
Extracteur de compétences techniques basé sur un dictionnaire hiérarchique.
Combine matching exact + gestion des aliases (variantes JS=JavaScript, etc.).
"""
import json
import re
from pathlib import Path
from typing import Optional

from loguru import logger


class SkillsExtractor:
    """Extrait les compétences d'un texte de CV via dictionnaire."""

    DICT_PATH = Path(__file__).parent.parent / "data" / "skills_dictionary.json"

    def __init__(self):
        self.dictionary: dict = {}
        self.flat_skills: dict[str, str] = {}  # variante (lowercase) -> nom canonique
        self._load_dictionary()

    def _load_dictionary(self):
        """Charge le JSON et construit l'index plat pour le matching."""
        with open(self.DICT_PATH, "r", encoding="utf-8") as f:
            self.dictionary = json.load(f)

        self._build_flat_index()
        logger.info(f"Dictionnaire chargé : {len(self.flat_skills)} entrées indexées")

    def _build_flat_index(self):
        """Aplatit le dico en {variante_lowercase: nom_canonique}."""
        self.flat_skills = {}

        # Parcours récursif des catégories
        def walk(node):
            if isinstance(node, dict):
                if "skills" in node and "aliases" in node:
                    # Compétences canoniques
                    for skill in node["skills"]:
                        self.flat_skills[skill.lower()] = skill
                    # Aliases → pointent vers le nom canonique
                    for alias, canonical in node["aliases"].items():
                        self.flat_skills[alias.lower()] = canonical
                else:
                    for value in node.values():
                        walk(value)

        walk(self.dictionary)

    def extract(
        self,
        text: str,
        filtered_categories: Optional[list[str]] = None,
    ) -> dict:
        """
        Extrait les compétences présentes dans un texte.

        :param text: texte du CV
        :param filtered_categories: filtre optionnel (ex: ["informatique"])
        :return: dict avec found_skills et stats
        """
        if not text:
            return {"found_skills": [], "by_category": {}, "total": 0}

        text_lower = text.lower()
        found = set()

        # Matching avec word boundaries (\b) pour éviter les faux positifs
        # Ex: "Java" ne matche pas dans "JavaScript"
        # Normalise le texte : remplace tous les whitespaces (espaces, tabs, newlines)
        # par un espace simple pour gérer "Spring\nBoot" ou "Spring  Boot"
        text_normalized = re.sub(r'\s+', ' ', text_lower)

        for variant, canonical in self.flat_skills.items():
            # Échappe les caractères spéciaux regex
            escaped = re.escape(variant)
            # Tolère un ou plusieurs espaces dans les compétences multi-mots
            # Ex: "spring boot" matche "spring  boot" ou "spring\nboot"
            pattern_flexible = escaped.replace(r"\ ", r"[\s\-]+")
            pattern = rf"(?<![a-zA-Z0-9]){pattern_flexible}(?![a-zA-Z0-9])"
            if re.search(pattern, text_normalized):
                found.add(canonical)

        # Catégorisation des compétences trouvées
        by_category = self._categorize(found, filtered_categories)

        return {
            "found_skills": sorted(found),
            "by_category": by_category,
            "total": len(found),
        }

    def _categorize(
        self,
        found_skills: set[str],
        filtered_categories: Optional[list[str]] = None,
    ) -> dict[str, list[str]]:
        """Regroupe les compétences trouvées par catégorie du dictionnaire."""
        result: dict[str, list[str]] = {}

        def walk(node, path: list[str]):
            if isinstance(node, dict):
                if "skills" in node:
                    category_path = ".".join(path)
                    matched = [s for s in node["skills"] if s in found_skills]
                    if matched:
                        result[category_path] = matched
                else:
                    for key, value in node.items():
                        if key in ("version", "language"):
                            continue
                        # Filtre par top-level si demandé
                        if not path and filtered_categories \
                                and key not in filtered_categories \
                                and key != "transversal":
                            continue
                        walk(value, path + [key])

        walk(self.dictionary, [])
        return result


# Singleton
skills_extractor = SkillsExtractor()