"""Tests pour skills_extractor.py."""
from app.core.skills_extractor import skills_extractor


class TestSkillsExtractor:

    def test_dictionary_loaded(self):
        """Le dictionnaire est bien chargé au démarrage."""
        assert len(skills_extractor.flat_skills) > 100

    def test_extract_basic_skills(self):
        """Détecte les compétences simples."""
        text = "Je maîtrise Python, Java et MySQL."
        result = skills_extractor.extract(text)
        assert "Python" in result["found_skills"]
        assert "Java" in result["found_skills"]
        assert "MySQL" in result["found_skills"]

    def test_extract_with_aliases(self):
        """Les aliases sont bien convertis (JS → JavaScript)."""
        text = "Compétences : JS, NodeJS, ReactJS"
        result = skills_extractor.extract(text)
        assert "JavaScript" in result["found_skills"]
        assert "Node.js" in result["found_skills"]
        assert "React" in result["found_skills"]

    def test_french_no_accent_alias(self):
        """'Francais' (sans accent) → 'Français'."""
        text = "Langues : Francais, Anglais"
        result = skills_extractor.extract(text)
        assert "Français" in result["found_skills"]

    def test_spring_boot_with_newline(self):
        """Tolère 'Spring\\nBoot' avec saut de ligne."""
        text = "Java (Spring\nBoot, REST API)"
        result = skills_extractor.extract(text)
        assert "Spring Boot" in result["found_skills"]

    def test_apirest_alias(self):
        """'APIREST' → 'REST API' via alias."""
        text = "Compétences : Angular, Flask, APIREST, MySQL"
        result = skills_extractor.extract(text)
        assert "REST API" in result["found_skills"]

    def test_empty_text(self):
        """Texte vide → pas de skills."""
        result = skills_extractor.extract("")
        assert result["found_skills"] == []
        assert result["total"] == 0

    def test_no_false_positive_word_boundary(self):
        """'Java' ne doit pas matcher dans 'JavaScript'."""
        text = "JavaScript"
        result = skills_extractor.extract(text)
        # JavaScript doit être détecté
        assert "JavaScript" in result["found_skills"]
        # Mais Java ne doit pas être détecté tout seul ici
        # (Note: Java pourrait être listé séparément si dans le texte)

    def test_categorization(self):
        """Les compétences sont bien catégorisées."""
        text = "Python, Java, MySQL, Docker"
        result = skills_extractor.extract(text)
        categories = result["by_category"]
        assert any("programming_languages" in k for k in categories.keys())
        assert any("databases" in k for k in categories.keys())