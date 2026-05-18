"""
================================================================================
CV SECTIONIZER — Découpe un CV en sections nommées
================================================================================

ROLE :
Prendre le texte brut d'un CV et le découper en sections logiques :
    - summary       (résumé / profil)
    - experience    (stages, expériences pro)
    - education     (formation, diplômes)
    - skills        (compétences techniques)
    - projects      (projets perso, académiques)
    - languages     (langues)
    - soft_skills   (qualités humaines)
    - certifications
    - associations  (vie associative, clubs)
    - other         (le reste non classé)

POURQUOI :
Plutôt que de scanner tout le CV à la recherche de mots-clés (fragile),
on isole d'abord la bonne section, puis on travaille DEDANS.
Cela rend le scorer beaucoup plus robuste face aux CVs très variés.

ALGORITHME :
1. Normaliser le texte (Unicode exotiques, espaces multiples)
2. Découper le texte en lignes
3. Pour chaque ligne, vérifier si elle ressemble à un titre de section
   (mot connu + ligne courte + souvent en MAJUSCULES)
4. Assigner toutes les lignes suivantes à cette section, jusqu'au prochain titre
================================================================================
"""

import re
import unicodedata
from typing import Dict, List


# =============================================================================
# DICTIONNAIRE DES TITRES DE SECTION (multilingue FR/EN)
# =============================================================================
# Chaque section a une liste de mots-clés possibles dans son titre.
# On normalise tout en minuscules avant la comparaison.
# =============================================================================
SECTION_KEYWORDS: Dict[str, List[str]] = {
    "summary": [
        "summary", "profile", "profil", "about me", "à propos",
        "presentation", "présentation", "objectif", "objective",
    ],

    "experience": [
        "experience", "expérience", "experiences", "expériences",
        "work experience", "professional experience", "expérience professionnelle",
        "stage", "stages", "stage professionnel", "stages professionnels",
        "internship", "internships", "parcours professionnel",
        "emploi", "career", "employment", "professional background",
    ],

    "education": [
        "education", "éducation", "formation", "formations",
        "formation académique", "academic background", "academic",
        "studies", "études", "diplome", "diplôme", "diplômes",
        "scolarité", "parcours scolaire", "parcours académique",
    ],

    "skills": [
        "skills", "compétences", "compétance",  # "compétance" = faute fréquente
        "competences", "technical skills", "compétences techniques",
        "hard skills", "savoir-faire", "expertise", "technologies",
        "tech stack",
    ],

    "soft_skills": [
        "soft skills", "soft-skills", "compétences douces",
        "qualités personnelles", "qualités humaines", "savoir-être",
        "personal skills", "personality",
    ],

    "projects": [
        "projects", "projets", "réalisations", "realisations",
        "portfolio", "academic projects", "projets académiques",
        "personal projects", "projets personnels", "main projects",
    ],

    "languages": [
        "languages", "langues", "linguistic skills", "language skills",
        "compétences linguistiques",
    ],

    "certifications": [
        "certifications", "certificats", "certificates",
        "formation complémentaire", "formation complimentaire",  # faute fréquente
        "formations complémentaires", "additional training",
        "training", "trainings",
    ],

    "associations": [
        "associations", "vie associative", "experience associative",
        "exerience associative",  # faute fréquente vue sur Yesmine
        "volunteering", "volunteer", "bénévolat", "extra-curricular",
        "activities", "activités", "clubs", "engagement",
    ],

    "interests": [
        "interests", "centres d'intérêt", "centres d'interet",
        "hobbies", "loisirs", "passions",
    ],

    "contact": [
        "contact", "coordonnées", "informations personnelles",
        "personal information",
    ],

    "awards": [
        "awards", "prix", "distinctions", "achievements",
        "awards/activities", "récompenses",
    ],
}


# =============================================================================
# NORMALISATION UNICODE (réutilisée depuis scorer.py)
# =============================================================================
def _normalize_text(text: str) -> str:
    """Nettoie les caractères Unicode exotiques pour faciliter le matching."""
    if not text:
        return ""

    replacements = {
        "İ": "I", "ı": "i",
        "Ş": "S", "ş": "s",
        "Ğ": "G", "ğ": "g",
        "ᵉ": "e", "ⁿ": "n", "ᵗ": "t", "ʳ": "r",
        "ᵈ": "d", "ᵘ": "u", "ˢ": "s",
        "’": "'", "‘": "'",
        "–": "-", "—": "-",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


# =============================================================================
# DÉTECTION : la ligne est-elle un titre de section ?
# =============================================================================
def _is_section_header(line: str) -> tuple[bool, str | None]:
    """
    Détermine si une ligne ressemble à un titre de section.

    Critères (au moins 2 sur 3 doivent être vrais) :
      (1) Ligne courte (< 50 caractères de contenu utile)
      (2) Contient un mot-clé connu de section
      (3) Souvent en MAJUSCULES, ou en gras, ou suivie d'un séparateur

    Retourne (True, "experience") ou (False, None).
    """
    if not line or len(line.strip()) == 0:
        return False, None

    # Nettoyer la ligne : enlever ponctuation excessive et espaces multiples
    cleaned = line.strip()
    # On retire les ":" finaux, les "-", "_", "=" qui servent de séparateurs
    cleaned_for_match = re.sub(r"[:\-_=*•·►▶◆■▪]+\s*$", "", cleaned).strip()
    cleaned_for_match = re.sub(r"^\s*[•·►▶◆■▪]+\s*", "", cleaned_for_match)
    cleaned_lower = cleaned_for_match.lower()

    # Critère (1) : ligne courte
    is_short = len(cleaned_lower) <= 50

    # Critère (3) : majuscules (au moins 50% des lettres en MAJ)
    letters = [c for c in cleaned if c.isalpha()]
    if letters:
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        is_mostly_upper = upper_ratio >= 0.5
    else:
        is_mostly_upper = False

    # Critère (2) : mot-clé de section présent
    matched_section = None
    for section_name, keywords in SECTION_KEYWORDS.items():
        for kw in keywords:
            # Match strict : la ligne EST le mot-clé (ou contient peu d'autres mots)
            # On veut "EXPÉRIENCE" ou "EXPÉRIENCE PROFESSIONNELLE", pas "j'ai de l'expérience"
            if cleaned_lower == kw:
                matched_section = section_name
                break
            # Match flexible : la ligne commence par le mot-clé et reste courte
            if cleaned_lower.startswith(kw) and len(cleaned_lower) <= len(kw) + 25:
                matched_section = section_name
                break
            # Match : le mot-clé est dans la ligne et la ligne est très courte
            if kw in cleaned_lower and len(cleaned_lower) <= 35:
                matched_section = section_name
                break
        if matched_section:
            break

    if not matched_section:
        return False, None

    # Combinaison de critères : il faut au moins (court ET keyword) OU (keyword ET majuscules)
    if is_short and matched_section:
        return True, matched_section
    if matched_section and is_mostly_upper:
        return True, matched_section

    return False, None


# =============================================================================
# FONCTION PRINCIPALE
# =============================================================================
def split_into_sections(text: str) -> Dict[str, str]:
    """
    Découpe le CV en sections nommées.

    Args:
        text : Texte brut du CV (après extraction PDF)

    Returns:
        Dictionnaire {section_name: section_content}
        Exemple :
        {
            "summary": "Mohamed Aziz Mesfar, Computer Science student...",
            "experience": "Mobile Department Leader... Delivery App... PFE WEDTECT...",
            "education": "Diploma in Computer Science... High School...",
            ...
        }

        Si une section n'est pas trouvée, elle est absente du dictionnaire.
        Le contenu avant toute section détectée est mis dans "_header".
    """
    if not text:
        return {}

    normalized = _normalize_text(text)
    lines = normalized.split("\n")

    sections: Dict[str, List[str]] = {}
    current_section = "_header"  # avant la première section détectée
    sections[current_section] = []

    for line in lines:
        is_header, section_name = _is_section_header(line)

        if is_header and section_name:
            # Nouvelle section détectée → on bascule
            current_section = section_name
            if current_section not in sections:
                sections[current_section] = []
            # On NE met PAS la ligne de titre dans le contenu (sauf debug)
        else:
            # Ligne normale → on l'ajoute à la section courante
            sections[current_section].append(line)

    # Convertir les listes en chaînes
    result = {
        name: "\n".join(lines).strip()
        for name, lines in sections.items()
        if "\n".join(lines).strip()  # ignorer les sections vides
    }

    return result


# =============================================================================
# UTILITAIRE : récupérer une section avec fallback
# =============================================================================
def get_section(sections: Dict[str, str], *names: str, default: str = "") -> str:
    """
    Récupère la première section trouvée parmi une liste de noms.

    Exemple :
        text = get_section(sections, "experience", "summary", default="")
        → renvoie le contenu de "experience" si trouvé,
          sinon "summary", sinon "".
    """
    for name in names:
        if name in sections and sections[name]:
            return sections[name]
    return default


# =============================================================================
# UTILITAIRE : retrouver le texte complet d'une section "élargie"
# =============================================================================
def get_combined_text(sections: Dict[str, str], section_names: List[str]) -> str:
    """
    Combine plusieurs sections en un seul texte.
    Utile pour chercher dans "experience + projects" par exemple.
    """
    parts = [sections[n] for n in section_names if n in sections and sections[n]]
    return "\n\n".join(parts)