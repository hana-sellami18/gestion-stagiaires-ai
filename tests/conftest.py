"""Fixtures partagées par tous les tests."""
import pytest


@pytest.fixture
def sample_cv_data():
    """CV factice pour tester le scoring sans dépendre de PyMuPDF."""
    return {
        "extraction": {
            "method": "native",
            "num_pages": 1,
            "char_count": 2000,
        },
        "skills": {
            "found_skills": [
                "Java", "Spring Boot", "MySQL", "Git", "Docker",
                "Python", "REST API", "Français", "Anglais"
            ],
            "by_category": {
                "transversal.languages_human": ["Français", "Anglais"],
                "informatique.programming_languages": ["Java", "Python"],
                "informatique.web_backend": ["Spring Boot", "REST API"],
                "informatique.databases": ["MySQL"],
                "informatique.devops_cloud": ["Docker"],
                "informatique.tools_versioning": ["Git"],
            },
            "total": 9,
        },
        "ner": {
            "organizations": ["Institut International de Technologie"],
            "education_lines": [
                "Licence en Génie Logiciel",
                "Institut International de Technologie",
            ],
            "years": [2022, 2024],
        },
        "raw_text_preview": "CV étudiant licence informatique avec compétences Spring Boot et MySQL...",
    }


@pytest.fixture
def sample_subject():
    """Sujet de stage de test."""
    from app.models.schemas import StageSubject
    return StageSubject(
        title="Stage Backend Java/Spring Boot",
        description="Développement API REST avec Spring Boot et MySQL.",
        required_skills=["Java", "Spring Boot", "MySQL", "REST API"],
        filiere="Informatique",
        cycle="Licence",
    )


@pytest.fixture
def empty_cv_data():
    """CV vide pour tester les cas limites."""
    return {
        "extraction": {"method": "native", "num_pages": 0, "char_count": 0},
        "skills": {"found_skills": [], "by_category": {}, "total": 0},
        "ner": {"organizations": [], "education_lines": [], "years": []},
        "raw_text_preview": "",
    }