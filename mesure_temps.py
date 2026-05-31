"""Mesure les temps d'execution du pipeline IA sur un CV."""
import time
from pathlib import Path

from app.core.cv_parser import cv_parser
from app.core.scorer import scorer
from app.models.schemas import StageSubject

# --- A ADAPTER : un CV de test et un sujet ---
CV_PATH = r"C:\Users\ousse\Downloads\AI-main\AI-main\gold_dataset\cvs\CV_Ahmed_benAli.pdf" # mets un vrai chemin

subject = StageSubject(
    title="Stage Ingénieur IA – Analyse et Recommandation Automatique",
    description="Développement d’une plateforme basée sur l’IA pour l’analyse sémantique, le scoring intelligent et la génération de recommandations à partir de données non structurées.",
    competences_cibles=[
        "Python",
        "LLM",
        "Machine Learning",
        "NLP",
        "FastAPI",
        "Vector Database",
        "Docker",
        "API Integration"
    ],
    filiere="Informatique",
    cycle="master"
)

print("=" * 50)
print("MESURE DES TEMPS DU PIPELINE IA")
print("=" * 50)

# Etape 1 : parsing complet du CV (PDF + anonymisation + NER)
t0 = time.perf_counter()
cv_data = cv_parser.parse(Path(CV_PATH))
t1 = time.perf_counter()
print(f"Parsing CV (PDF + anonym. + NER) : {t1 - t0:.2f} s")

# Etape 2 : scoring complet (extraction LLM + triangulation + score)
t2 = time.perf_counter()
result = scorer.score(cv_data, subject)
t3 = time.perf_counter()
print(f"Scoring (LLM + triangulation)    : {t3 - t2:.2f} s")

# Total
print("-" * 50)
print(f"TOTAL pipeline                   : {t3 - t0:.2f} s")
print("=" * 50)
print(f"Score final : {result.final_score}/100 [{result.recommendation}]")