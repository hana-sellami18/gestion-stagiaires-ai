"""Tests pour scorer.py."""
import pytest
from app.core.scorer import scorer, WEIGHTS, THRESHOLD_ADAPTE, THRESHOLD_PARTIELLEMENT


class TestScorer:

    def test_weights_sum_to_one(self):
        """La somme des poids vaut 1.0 (validation pondération)."""
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"Somme des poids = {total}, attendu 1.0"

    def test_weights_correct_values(self):
        """Pondération V5 : 40 / 25 / 15 / 10 / 5 / 5."""
        assert WEIGHTS["skills"]      == 0.40
        assert WEIGHTS["formation"]   == 0.25
        assert WEIGHTS["experience"]  == 0.15
        assert WEIGHTS["soft_skills"] == 0.10
        assert WEIGHTS["languages"]   == 0.05
        assert WEIGHTS["motivation"]  == 0.05

    def test_perfect_match_high_score(self, sample_cv_data, sample_subject):
        """CV avec toutes les skills requises → score élevé."""
        result = scorer.score(sample_cv_data, sample_subject)
        assert result.final_score >= 70
        assert result.recommendation == "ADAPTE"
        assert len(result.pillars["skills"].matched) >= 3
        assert len(result.pillars["skills"].missing) <= 1

    def test_empty_cv_low_score(self, empty_cv_data, sample_subject):
        """CV vide → score faible."""
        result = scorer.score(empty_cv_data, sample_subject)
        assert result.final_score < 50
        assert result.recommendation in ["PEU_ADAPTE", "PARTIELLEMENT_ADAPTE"]

    def test_score_in_valid_range(self, sample_cv_data, sample_subject):
        """Le score est toujours entre 0 et 100."""
        result = scorer.score(sample_cv_data, sample_subject)
        assert 0 <= result.final_score <= 100

    def test_pillars_present(self, sample_cv_data, sample_subject):
        """Les 6 piliers V5 sont tous présents dans la sortie."""
        result = scorer.score(sample_cv_data, sample_subject)
        assert "skills"      in result.pillars
        assert "formation"   in result.pillars
        assert "experience"  in result.pillars
        assert "soft_skills" in result.pillars
        assert "languages"   in result.pillars
        assert "motivation"  in result.pillars

    def test_recommendation_thresholds(self, sample_cv_data, sample_subject):
        """Les recommandations correspondent aux seuils V5."""
        result = scorer.score(sample_cv_data, sample_subject)
        if result.final_score >= THRESHOLD_ADAPTE:
            assert result.recommendation == "ADAPTE"
        elif result.final_score >= THRESHOLD_PARTIELLEMENT:
            assert result.recommendation == "PARTIELLEMENT_ADAPTE"
        else:
            assert result.recommendation == "PEU_ADAPTE"

    def test_justification_not_empty(self, sample_cv_data, sample_subject):
        """La justification textuelle est générée."""
        result = scorer.score(sample_cv_data, sample_subject)
        assert len(result.justification) > 50
        assert "Compétences" in result.justification or "🔧" in result.justification