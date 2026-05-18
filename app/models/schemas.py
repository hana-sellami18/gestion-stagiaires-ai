"""Schemas Pydantic — alignes sur le backend Spring Boot ASM.

VERSION v10 :
- Ajout du champ optionnel `confidence` dans PillarScore (retro-compatible)
- Ajout du champ optionnel `extraction_metadata` dans CompatibilityScore
  pour exposer les sources de triangulation a l'UI RH (AI Act art. 13).
"""
from typing import Optional, Any
from pydantic import BaseModel, Field


# ============================================================
# INPUT : Le sujet de stage (format aligne backend Spring Boot)
# ============================================================

class StageSubject(BaseModel):
    """
    Sujet de stage — format aligne sur l'entite SujetStage (Spring Boot).

    Le scorer applique une repartition automatique des competences :
    - 60% premieres -> core_skills (poids 1.0)
    - 30% suivantes -> important_skills (poids 0.6)
    - 10% dernieres -> bonus_skills (poids 0.3)
    """
    title: str = Field(..., description="Titre du sujet (mappe 'titre' cote backend)")
    description: str = Field(..., description="Description complete")

    competences_cibles: list[str] = Field(
        default_factory=list,
        description="Liste des competences requises, par ordre de priorite decroissant"
    )

    filiere: Optional[str] = Field(None, description="Filiere cible (nom)")
    cycle: Optional[str] = Field(None, description="Cycle cible (nom)")

    required_languages: list[str] = Field(
        default_factory=list,
        description="Langues requises (optionnel)"
    )


# ============================================================
# OUTPUT : Le score de compatibilite
# ============================================================

class PillarScore(BaseModel):
    """Score detaille pour un pilier."""
    score: float = Field(..., ge=0, le=100, description="Score 0-100")
    weight: float = Field(..., description="Poids du pilier")
    weighted: float = Field(..., description="Score pondere (score * weight)")
    matched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)

    # NOUVEAU v10 (optionnel, retro-compatible)
    confidence: Optional[str] = Field(
        None,
        description="Niveau de confiance d'extraction : high | medium | low (AI Act art. 13)"
    )


class ExtractionMetadata(BaseModel):
    """
    Metadonnees d'extraction (triangulation regex / NER / LLM).
    Permet a l'UI RH de comprendre le niveau de fiabilite du score.
    Conforme AI Act articles 13 (transparence) et 14 (supervision humaine).
    """
    overall_confidence: str = Field(..., description="high | medium | low")
    llm_used: bool = Field(..., description="LLM a-t-il ete utilise ?")

    # Detail par champ extrait
    stages_count: Optional[int] = None
    stages_confidence: Optional[str] = None
    stages_sources: Optional[dict] = None

    cycle_detected: Optional[str] = None
    cycle_confidence: Optional[str] = None

    annee_detected: Optional[int] = None
    annee_confidence: Optional[str] = None

    is_pfe: Optional[bool] = None
    pfe_confidence: Optional[str] = None

    entreprises_detected: list[str] = Field(default_factory=list)

    requires_human_validation: bool = Field(
        False,
        description="True si confiance faible -> validation RH requise (AI Act art. 14)"
    )


class CompatibilityScore(BaseModel):
    """Resultat complet du scoring."""
    final_score: float = Field(..., ge=0, le=100)
    recommendation: str = Field(..., description="ADAPTE | PARTIELLEMENT_ADAPTE | PEU_ADAPTE | ADAPTE_A_VERIFIER")
    recommendation_label: str = Field(..., description="Texte humain")
    pillars: dict[str, PillarScore]
    justification: str = Field(..., description="Explication textuelle")
    semantic_similarity: float = Field(..., description="Similarite SBERT 0-1")
    audit_id: Optional[str] = Field(None)
    filename: Optional[str] = Field(None)
    cv_info: Optional[dict[str, Any]] = Field(None)

    # NOUVEAU v10 (optionnel, retro-compatible)
    extraction_metadata: Optional[ExtractionMetadata] = Field(
        None,
        description="Metadonnees de triangulation (AI Act conformite)"
    )