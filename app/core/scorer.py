"""
================================================================================
SCORER v10 — Architecture finale ASM avec triangulation
================================================================================

CHANGEMENTS PAR RAPPORT A v9 :

1. DELEGATION DE L'EXTRACTION
   Les methodes _count_real_stages() et detect_cycle_info() sont REMPLACEES
   par un appel a cv_intelligence.extract_intelligent_info() qui combine :
       - Regex (rapide)
       - NER (existant)
       - LLM (LLaMA 3.1 via Ollama)
   et fait voter les 3 methodes.

2. CHAMP CONFIDENCE
   Chaque pilier herite maintenant d'un niveau de confiance (high/medium/low)
   transmis a l'UI RH pour signaler les cas necessitant validation humaine.

3. PILIER SOFT SKILLS UTILISE LE NER
   On utilise directement les soft skills extraites par le NER en priorite,
   au lieu de chercher une section dediee (souvent absente).

CONFORMITE AI ACT :
   - Art. 13 (transparence) : justification detaillee des sources
   - Art. 14 (supervision humaine) : alerte si confiance < high
================================================================================
"""

import re
from typing import Optional
from loguru import logger

from app.core.sbert_client import get_sbert
from app.core import cv_intelligence
from app.models.schemas import (
    StageSubject,
    CompatibilityScore,
    PillarScore,
    ExtractionMetadata,
)


# =============================================================================
# PONDERATIONS v10 (inchangees par rapport a v9)
# =============================================================================
WEIGHTS = {
    "skills":      0.50,
    "experience":  0.13,
    "projects":    0.15,
    "formation":   0.10,
    "soft_skills": 0.05,
    "languages":   0.04,
    "motivation":  0.03,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 0.001


# =============================================================================
# SEUILS (inchanges)
# =============================================================================
THRESHOLD_ADAPTE = 70
THRESHOLD_PARTIELLEMENT = 50
GUARDRAIL_SKILLS_SCORE = 25
GUARDRAIL_SKILLS_COUNT = 4

SBERT_THRESHOLD = 0.70
APPROX_MATCH_WEIGHT = 0.6


# =============================================================================
# BLACKLISTS (inchangees)
# =============================================================================
SOFT_SKILLS_BLACKLIST = {
    "communication", "autonomie", "rigueur", "gestion du temps",
    "dynamique", "adaptabilite", "esprit d'equipe", "leadership",
    "creativite", "curiosite", "motivation", "esprit analytique",
    "resolution de problemes", "travail en equipe", "perseverance",
    "polyvalence", "organisation", "flexibilite", "proactif",
    "initiative", "ponctualite", "serieux", "implique",
    "teamwork", "problem solving", "analytical",
}

LANGUAGE_KEYWORDS = {
    "francais": ["francais", "francais","français", "french", "francophone", "dalf", "delf"],
    "anglais":  ["anglais", "english", "anglophone", "toeic", "toefl", "ielts"],
    "arabe":    ["arabe", "arabic"],
    "allemand": ["allemand", "german", "deutsch"],
    "espagnol": ["espagnol", "spanish", "espanol"],
}

MOTIVATION_KEYWORDS = [
    "objectif", "motivation", "souhait", "aspiration", "ambition", "interet",
    "passionne", "passionnee", "enthousiaste", "desireux", "desireuse",
    "contribuer", "apporter", "developper", "apprendre", "evoluer",
    "stage", "pfe", "projet de fin d'etudes", "acquerir", "mettre en pratique",
]


# =============================================================================
# CLASSE PRINCIPALE
# =============================================================================
class CompatibilityScorer:
    """Scorer v10 — Avec triangulation regex/NER/LLM."""

    def score(self, cv_data: dict, subject: StageSubject) -> CompatibilityScore:
        # =====================================================================
        # ETAPE 1 : EXTRACTION INTELLIGENTE (le grand changement v10)
        # =====================================================================
        cv_text = cv_data.get("raw_text_preview", "")
        organizations = cv_data.get("ner", {}).get("organizations", [])

        intelligence = cv_intelligence.extract_intelligent_info(
            cv_text=cv_text,
            organizations=organizations,
            use_llm=True,  # mettre False pour tests rapides
        )

        cv_data["_intelligence"] = intelligence
        cv_data["_sections"] = intelligence["sections"]

        logger.info(
            f"Intelligence : stages={intelligence['stages']['value']} "
            f"({intelligence['stages']['confidence']}) | "
            f"cycle={intelligence['cycle']['value']} "
            f"annee={intelligence['annee']['value']} | "
            f"PFE={intelligence['is_pfe']['value']} | "
            f"confiance globale={intelligence['overall_confidence']}"
        )

        # =====================================================================
        # ETAPE 2 : CALCUL DES PILIERS
        # =====================================================================
        skills_p     = self._score_skills(cv_data, subject)
        experience_p = self._score_experience(cv_data, intelligence)
        projects_p   = self._score_projects(cv_data, intelligence)
        formation_p  = self._score_formation(cv_data, intelligence)
        soft_p       = self._score_soft_skills(cv_data, intelligence)
        languages_p  = self._score_languages(cv_data, subject)
        motivation_p = self._score_motivation(cv_data, subject)

        # Score final
        final = round(
            skills_p.weighted + experience_p.weighted + projects_p.weighted +
            formation_p.weighted + soft_p.weighted + languages_p.weighted +
            motivation_p.weighted,
            1,
        )

        semantic = self._semantic_similarity(cv_data, subject)
        skills_count = cv_data.get("skills", {}).get("total", 0)

        pillars = {
            "skills":      skills_p,
            "experience":  experience_p,
            "projects":    projects_p,
            "formation":   formation_p,
            "soft_skills": soft_p,
            "languages":   languages_p,
            "motivation":  motivation_p,
        }

        reco_code, reco_label = self._build_recommendation(
            final, skills_p.score, skills_count,
            intelligence["overall_confidence"]
        )

        justification = self._build_justification(
            pillars, final, reco_label, semantic, intelligence
        )

        # ===== NOUVEAU v10 : metadonnees d'extraction =====
        metadata = self._build_metadata(intelligence)

        return CompatibilityScore(
            final_score=final,
            recommendation=reco_code,
            recommendation_label=reco_label,
            pillars=pillars,
            justification=justification,
            semantic_similarity=round(semantic, 3),
            extraction_metadata=metadata,
        )

    # =========================================================================
    # PILIER 1 — SKILLS (inchange)
    # =========================================================================
    def _score_skills(self, cv_data: dict, subject: StageSubject) -> PillarScore:
        cv_skills = set(cv_data.get("skills", {}).get("found_skills", []))
        cv_skills_tech = [s for s in cv_skills if s.lower() not in SOFT_SKILLS_BLACKLIST]
        cv_skills_tech_lower = {s.lower(): s for s in cv_skills_tech}

        required = subject.competences_cibles
        if not required:
            return PillarScore(
                score=50.0, weight=WEIGHTS["skills"],
                weighted=round(50.0 * WEIGHTS["skills"], 1),
                matched=list(cv_skills)[:10], missing=[],
                confidence="high",
            )

        matched, missing = [], []
        matched_points = 0.0
        total = len(required)
        sbert = get_sbert()

        for req in required:
            req_lower = req.lower()
            if req_lower in cv_skills_tech_lower:
                matched.append(req)
                matched_points += 1.0
                continue
            if len(req_lower) >= 4:
                partial = next(
                    (s for s_lower, s in cv_skills_tech_lower.items()
                     if (req_lower in s_lower or s_lower in req_lower)
                     and len(s_lower) >= 3),
                    None,
                )
                if partial:
                    matched.append(f"{req} (~{partial})")
                    matched_points += APPROX_MATCH_WEIGHT
                    continue
            if len(req) > 3 and cv_skills_tech:
                long_candidates = [s for s in cv_skills_tech if len(s) > 3]
                if long_candidates:
                    best, sim = sbert.best_match(req, long_candidates)
                    if sim >= SBERT_THRESHOLD:
                        matched.append(f"{req} (~SBERT:{best}, sim={sim:.2f})")
                        matched_points += APPROX_MATCH_WEIGHT
                        continue
            missing.append(req)

        base_score = (matched_points / total) * 100 if total > 0 else 0
        total_skills_count = cv_data.get("skills", {}).get("total", 0)
        richness_bonus = 3.0 if (base_score >= 40 and total_skills_count >= 20) else 0.0
        score = min(base_score + richness_bonus, 100.0)

        return PillarScore(
            score=round(score, 1), weight=WEIGHTS["skills"],
            weighted=round(score * WEIGHTS["skills"], 1),
            matched=matched, missing=missing,
            confidence="high",  # competences = extraction deterministe = haute confiance
        )

    # =========================================================================
    # PILIER 2 — EXPERIENCE (utilise l'intelligence triangulee)
    # =========================================================================
    def _score_experience(self, cv_data: dict, intelligence: dict) -> PillarScore:
        stages_info = intelligence["stages"]
        cycle_info = intelligence["cycle"]
        confidence = stages_info["confidence"]

        stage_count = stages_info["value"] if stages_info["value"] is not None else 0
        cycle = cycle_info["value"] if cycle_info["value"] else "autre"
        is_advanced = cycle in ("master", "ingenieur")

        score = 0.0
        matched = []

        if not is_advanced:
            if stage_count >= 3:
                score = 100.0
                matched.append(f"{stage_count} stages detectes")
            elif stage_count == 2:
                score = 85.0
                matched.append("2 stages detectes")
            elif stage_count == 1:
                score = 65.0
                matched.append("1 stage detecte")
            else:
                score = 15.0
                matched.append("Aucun stage detecte")
        else:
            if stage_count >= 4:
                score = 100.0
            elif stage_count >= 3:
                score = 85.0
            elif stage_count == 2:
                score = 70.0
            elif stage_count == 1:
                score = 45.0
            else:
                score = 10.0
            matched.append(f"{stage_count} stages detectes (cycle {cycle})")

        # Bonus entreprises identifiees
        entreprises = intelligence["entreprises"]["value"]
        if entreprises:
            matched.append(f"Entreprises : {', '.join(entreprises[:3])}")

        missing = []
        if score < 40:
            missing.append("Peu d'experience detectee")
        if confidence == "low":
            missing.append("Confiance faible — validation humaine recommandee")

        return PillarScore(
            score=round(score, 1), weight=WEIGHTS["experience"],
            weighted=round(score * WEIGHTS["experience"], 1),
            matched=matched, missing=missing,
            confidence=confidence,
        )

    # =========================================================================
    # PILIER 3 — PROJETS
    # =========================================================================
    def _score_projects(self, cv_data: dict, intelligence: dict) -> PillarScore:
        raw_text = cv_data.get("raw_text_preview", "").lower()
        llm_data = intelligence.get("_raw_llm_result") or {}

        score = 0.0
        matched = []

        # Source 1 : LLM a compte les projets
        projets_count = llm_data.get("projets_count") if llm_data else None
        if projets_count is not None:
            if projets_count >= 5:
                score += 50
                matched.append(f"{projets_count} projets detectes (LLM)")
            elif projets_count >= 3:
                score += 35
                matched.append(f"{projets_count} projets detectes")
            elif projets_count >= 1:
                score += 20
                matched.append(f"{projets_count} projet(s) detecte(s)")

        # Source 2 : mots-cles fallback
        perso_keywords = ["github", "gitlab", "projet personnel", "side project",
                          "open source", "portfolio", "hackathon"]
        perso_count = sum(1 for kw in perso_keywords if kw in raw_text)
        if perso_count >= 2 and projets_count is None:
            score += 30
            matched.append("Projets perso/GitHub detectes")

        # PFE
        has_pfe = intelligence["is_pfe"]["value"] or (
            llm_data.get("has_pfe_project") if llm_data else False
        )
        if has_pfe:
            score += 20
            matched.append("Projet PFE detecte")

        # Richesse competences
        skills_count = cv_data.get("skills", {}).get("total", 0)
        if skills_count >= 25:
            score += 20
            matched.append(f"{skills_count} competences (tres polyvalent)")
        elif skills_count >= 15:
            score += 10

        # Engagement
        engagement_keywords = ["hackathon", "certification", "ieee", "club"]
        if sum(1 for kw in engagement_keywords if kw in raw_text) >= 2:
            score += 10
            matched.append("Engagement tech (clubs, certifs)")

        score = min(score, 100.0)
        missing = ["Peu de projets detectes"] if score < 30 else []

        # Confiance du pilier projets = confiance LLM si LLM dispo, sinon medium
        proj_confidence = "medium" if intelligence["_llm_used"] else "low"

        return PillarScore(
            score=round(score, 1), weight=WEIGHTS["projects"],
            weighted=round(score * WEIGHTS["projects"], 1),
            matched=matched, missing=missing,
            confidence=proj_confidence,
        )

    # =========================================================================
    # PILIER 4 — FORMATION
    # =========================================================================
    def _score_formation(self, cv_data: dict, intelligence: dict) -> PillarScore:
        education_lines = cv_data.get("ner", {}).get("education_lines", [])
        cycle = intelligence["cycle"]["value"]
        annee = intelligence["annee"]["value"]
        is_pfe = intelligence["is_pfe"]["value"]
        confidence = intelligence["annee"]["confidence"]

        score = 0.0
        matched = []
        missing = []

        if is_pfe:
            score += 80
            matched.append(f"Annee PFE detectee ({cycle or '?'} annee {annee or '?'})")
        elif annee:
            if cycle == "licence":
                score += 50 if annee == 2 else (20 if annee == 1 else 60)
                matched.append(f"Licence annee {annee}")
            elif cycle == "master":
                score += 60 if annee == 1 else 70
                matched.append(f"Master annee {annee}")
            elif cycle == "ingenieur":
                score += 60 if annee == 4 else (45 if annee == 3 else 30)
                matched.append(f"Ingenieur annee {annee}")
            else:
                score += 40
                matched.append(f"Annee {annee} (cycle inconnu)")
        else:
            score += 30
            missing.append("Annee dans le cycle non detectee")

        if len(education_lines) >= 2:
            score += 15
            matched.append(f"Parcours detaille ({len(education_lines)} etapes)")
        elif len(education_lines) >= 1:
            score += 5

        score = min(score, 100.0)

        return PillarScore(
            score=round(score, 1), weight=WEIGHTS["formation"],
            weighted=round(score * WEIGHTS["formation"], 1),
            matched=matched if matched else education_lines[:2],
            missing=missing,
            confidence=confidence,
        )

    # =========================================================================
    # PILIER 5 — SOFT SKILLS (NER + LLM)
    # =========================================================================
    def _score_soft_skills(self, cv_data: dict, intelligence: dict) -> PillarScore:
        # Source 1 : soft skills NER
        ner_soft = cv_data.get("skills", {}).get("by_category", {}).get(
            "transversal.soft_skills", []
        )

        # Source 2 : soft skills LLM
        llm_soft = intelligence["soft_skills"]["value"]

        all_soft = set(s.lower() for s in (ner_soft or []) + (llm_soft or []))
        count = len(all_soft)

        if count >= 6:
            score = 100.0
        elif count >= 4:
            score = 80.0
        elif count >= 2:
            score = 55.0
        elif count == 1:
            score = 35.0
        else:
            score = 25.0

        matched = sorted(all_soft)[:8]
        missing = ["Peu de soft skills detectees"] if count < 3 else []

        soft_confidence = "high" if (ner_soft and llm_soft) else "medium"

        return PillarScore(
            score=round(score, 1), weight=WEIGHTS["soft_skills"],
            weighted=round(score * WEIGHTS["soft_skills"], 1),
            matched=list(matched), missing=missing,
            confidence=soft_confidence,
        )

    # =========================================================================
    # PILIER 6 — LANGUES (inchange)
    # =========================================================================
    def _score_languages(self, cv_data: dict, subject: StageSubject) -> PillarScore:
        raw_text = cv_data.get("raw_text_preview", "").lower()

        detected = [
            lang.capitalize()
            for lang, keywords in LANGUAGE_KEYWORDS.items()
            if any(kw in raw_text for kw in keywords)
        ]

        score = min(len(detected) * 30, 90.0)
        if "Francais" in detected:
            score = max(score, 50.0)
        score = min(score, 100.0)

        missing = []
        if subject.required_languages:
            detected_lower = [l.lower() for l in detected]
            for lang in subject.required_languages:
                if lang.lower() not in detected_lower:
                    score = max(score - 20.0, 0.0)
                    missing.append(f"Langue requise non detectee : {lang}")

        return PillarScore(
            score=round(score, 1), weight=WEIGHTS["languages"],
            weighted=round(score * WEIGHTS["languages"], 1),
            matched=detected, missing=missing,
            confidence="high",
        )

    # =========================================================================
    # PILIER 7 — MOTIVATION (inchange)
    # =========================================================================
    def _score_motivation(self, cv_data: dict, subject: StageSubject) -> PillarScore:
        raw_text = cv_data.get("raw_text_preview", "").lower()

        found_keywords = [kw for kw in MOTIVATION_KEYWORDS if kw.lower() in raw_text]
        score = 0.0
        matched = []

        if len(found_keywords) >= 3:
            score += 50
            matched.append("Section motivation detectee")
        elif len(found_keywords) >= 1:
            score += 25

        title_words = subject.title.lower().split()
        title_matches = [w for w in title_words if len(w) > 4 and w in raw_text]
        if len(title_matches) >= 2:
            score += 30
        elif len(title_matches) == 1:
            score += 15

        if subject.filiere and subject.filiere.lower() in raw_text:
            score += 20

        score = min(score, 100.0)

        return PillarScore(
            score=round(score, 1), weight=WEIGHTS["motivation"],
            weighted=round(score * WEIGHTS["motivation"], 1),
            matched=matched,
            missing=[] if score >= 40 else ["Peu d'indicateurs de motivation"],
            confidence="medium",
        )

    # =========================================================================
    # SIMILARITE SEMANTIQUE
    # =========================================================================
    def _semantic_similarity(self, cv_data: dict, subject: StageSubject) -> float:
        cv_text = cv_data.get("raw_text_preview", "")
        if not cv_text:
            cv_text = " ".join(cv_data.get("skills", {}).get("found_skills", []))

        subject_text = (
            f"{subject.title}. {subject.description}. "
            f"Competences requises : {', '.join(subject.competences_cibles)}"
        )

        if not cv_text or not subject_text:
            return 0.0

        return get_sbert().similarity(cv_text, subject_text)

    # =========================================================================
    # RECOMMANDATION (avec prise en compte de la confiance)
    # =========================================================================
    def _build_recommendation(
        self, score: float, skills_score: float, skills_count: int,
        overall_confidence: str
    ) -> tuple[str, str]:
        # Garde-fou
        if skills_score < GUARDRAIL_SKILLS_SCORE or skills_count < GUARDRAIL_SKILLS_COUNT:
            return ("PEU_ADAPTE",
                    "Profil PEU ADAPTE — Competences techniques insuffisantes")

        # Confiance faible -> toujours demander validation humaine
        if overall_confidence == "low" and score >= THRESHOLD_ADAPTE:
            return ("ADAPTE_A_VERIFIER",
                    "Profil ADAPTE — Confiance faible, validation RH requise")

        if score >= THRESHOLD_ADAPTE:
            return ("ADAPTE", "Profil ADAPTE — Entretien fortement recommande")
        elif score >= THRESHOLD_PARTIELLEMENT:
            return ("PARTIELLEMENT_ADAPTE",
                    "Profil PARTIELLEMENT ADAPTE — A considerer")
        return ("PEU_ADAPTE", "Profil PEU ADAPTE — Validation humaine conseillee")

    # =========================================================================
    # METADONNEES (nouveau v10)
    # =========================================================================
    def _build_metadata(self, intelligence: dict) -> ExtractionMetadata:
        """Construit les metadonnees d'extraction pour l'AI Act conformite."""
        overall = intelligence["overall_confidence"]
        requires_validation = (overall == "low")

        return ExtractionMetadata(
            overall_confidence=overall,
            llm_used=intelligence["_llm_used"],
            stages_count=intelligence["stages"]["value"],
            stages_confidence=intelligence["stages"]["confidence"],
            stages_sources={
                k: v for k, v in intelligence["stages"]["sources"].items()
                if v is not None
            },
            cycle_detected=intelligence["cycle"]["value"],
            cycle_confidence=intelligence["cycle"]["confidence"],
            annee_detected=intelligence["annee"]["value"],
            annee_confidence=intelligence["annee"]["confidence"],
            is_pfe=intelligence["is_pfe"]["value"],
            pfe_confidence=intelligence["is_pfe"]["confidence"],
            entreprises_detected=intelligence["entreprises"]["value"],
            requires_human_validation=requires_validation,
        )

    # =========================================================================
    # JUSTIFICATION (enrichie avec sources)
    # =========================================================================
    def _build_justification(
        self, pillars: dict, final: float, reco: str,
        semantic: float, intelligence: dict
    ) -> str:
        lines = [
            f"Score final : {final}/100 — {reco}",
            f"Confiance globale extraction : {intelligence['overall_confidence'].upper()}",
            "",
            f"Ponderation v10 :",
            f"  Competences 50% · Experience 13% · Projets 15%",
            f"  Formation 10% · Soft Skills 5% · Langues 4% · Motivation 3%",
            "",
            f"Triangulation des sources (regex + NER + LLM) :",
            f"  - Stages : {intelligence['stages']['value']} "
            f"(confiance: {intelligence['stages']['confidence']})",
            f"    Sources : {intelligence['stages']['sources']}",
            f"  - Cycle  : {intelligence['cycle']['value']} "
            f"(confiance: {intelligence['cycle']['confidence']})",
            f"  - Annee  : {intelligence['annee']['value']} "
            f"(confiance: {intelligence['annee']['confidence']})",
            f"  - PFE    : {intelligence['is_pfe']['value']} "
            f"(confiance: {intelligence['is_pfe']['confidence']})",
            f"  - LLM utilise : {intelligence['_llm_used']}",
            f"  - Similarite SBERT : {round(semantic, 3)}",
            "",
        ]

        for name, label, emoji in [
            ("skills",      "Competences", "[S]"),
            ("experience",  "Experience",  "[E]"),
            ("projects",    "Projets",     "[P]"),
            ("formation",   "Formation",   "[F]"),
            ("soft_skills", "Soft skills", "[SS]"),
            ("languages",   "Langues",     "[L]"),
            ("motivation",  "Motivation",  "[M]"),
        ]:
            p = pillars[name]
            conf = f" (conf: {p.confidence})" if p.confidence else ""
            lines.append(
                f"{emoji} {label} — {p.score}/100 (contribution {p.weighted}/100){conf}"
            )
            if p.matched:
                lines.append(f"   OK: {' | '.join(str(m) for m in p.matched[:4])}")
            if p.missing:
                lines.append(f"   /!\\ {p.missing[0]}")
            lines.append("")

        return "\n".join(lines)


# =============================================================================
# SINGLETON
# =============================================================================
scorer = CompatibilityScorer()
