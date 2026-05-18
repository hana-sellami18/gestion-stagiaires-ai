"""Test rapide du nouveau scorer avec le format backend."""
from app.core.cv_parser import cv_parser
from app.core.scorer import scorer
from app.models.schemas import StageSubject

# 1. Charger un CV
cv_path = "gold_dataset/cvs/yesmine cherif.pdf"
with open(cv_path, "rb") as f:
    cv_data = cv_parser.parse(f.read())

print("=" * 70)
print(f"CV analysé : {cv_path}")
print(f"Compétences détectées dans le CV : {cv_data['skills']['total']}")
print(f"Liste : {cv_data['skills']['found_skills']}")
print("=" * 70)

# 2. Créer un sujet au NOUVEAU format
subject = StageSubject(
    title="Stage Développeur Backend Java/Spring Boot",
    description="Développement d'une API REST avec Spring Boot, Java 17, base MySQL, déploiement Docker.",
    competences_cibles=[
        "Java", "Spring Boot", "REST API", "MySQL", "JPA",
        "Hibernate", "SQL", "Docker", "Git", "Microservices", "Maven"
    ],
    filiere="Informatique",
    cycle="Licence",
)

# 3. Scorer
result = scorer.score(cv_data, subject)

# 4. Afficher
print(f"\n>>> Score final : {result.final_score}/100")
print(f">>> Recommandation : {result.recommendation}")
print(f">>> Label : {result.recommendation_label}")
print(f"\n--- Pilier Skills ---")
print(f"  Score : {result.pillars['skills'].score}/100")
print(f"  Matched ({len(result.pillars['skills'].matched)}) : {result.pillars['skills'].matched}")
print(f"  Missing ({len(result.pillars['skills'].missing)}) : {result.pillars['skills'].missing}")

print(f"\n--- Pilier Formation ---")
print(f"  Score : {result.pillars['formation'].score}/100")
print(f"  Matched : {result.pillars['formation'].matched}")

print(f"\n--- Pilier Expérience ---")
print(f"  Score : {result.pillars['experience'].score}/100")
print(f"  Matched : {result.pillars['experience'].matched}")