"""
Verifie que tout est bien en place AVANT de re-evaluer.
Place a la racine du projet et lance : python verify_fix.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import inspect
from app.core import cv_parser as cv_parser_module
from app.core.cv_parser import detect_cycle, cv_parser

print("=" * 70)
print("VERIFICATION 1 : cv_parser.py est-il en v11.0 ?")
print("=" * 70)
source = inspect.getsource(cv_parser_module)
if "v11.0" in source and "_detect_cycle_from_timeline" in source:
    print("OK : cv_parser.py est en v11.0 avec timeline")
else:
    print("!!! ECHEC : cv_parser.py n'a PAS ete remplace !!!")
    print("Remplace bien le fichier app/core/cv_parser.py")
    sys.exit(1)

print()
print("=" * 70)
print("VERIFICATION 2 : test direct sur le CV d'Ahmed")
print("=" * 70)

# Texte d'Ahmed reconstitue d'apres education_lines
cv_ahmed = """
Ahmed Ben Ali
ahmed@example.com

Etudiant en 1ere annee Master Big Data a l'ENIS Sfax, passionne par
l'analyse de donnees, le machine learning et le deep learning.

FORMATION

2025 - Present | Master Big Data & Intelligence Artificielle
Master Big Data & IA - ENIS Sfax

2022 - 2025 | Licence Fondamentale en Informatique
Faculte des Sciences

EXPERIENCE
Stage chez IBM

SKILLS
Python, Java, SQL, Docker, Machine Learning
"""

result = detect_cycle(cv_ahmed)
print(f"Cycle detecte pour texte simule : {result}")
if result == "master":
    print("OK : la fonction marche correctement")
else:
    print(f"!!! La fonction retourne '{result}' au lieu de 'master' !!!")
    sys.exit(1)

print()
print("=" * 70)
print("VERIFICATION 3 : parser le VRAI PDF d'Ahmed")
print("=" * 70)
# Ajuste le chemin
CV_PATH = r"C:\Users\ousse\Downloads\AI-main\AI-main\gold_dataset\cvs\CV_Ahmed_benAli.pdf"

if not Path(CV_PATH).exists():
    print(f"!!! Fichier non trouve : {CV_PATH}")
    print("Ajuste la variable CV_PATH dans ce script")
    sys.exit(1)

parsed = cv_parser.parse(CV_PATH)
print(f"Cycle final retourne par parse() : {parsed['cycle']}")
print(f"Filiere : {parsed['filiere']}")

if parsed['cycle'] == "master":
    print()
    print("*** SUCCES TOTAL : le bug est corrige ***")
    print()
    print("Etape suivante :")
    print("  1. Vide le cache : Remove-Item cache\\llm_cv_cache.json")
    print("  2. Redemarre FastAPI (Ctrl+C puis relance uvicorn)")
    print("  3. Re-evalue Ahmed via l'API")
else:
    print(f"!!! ECHEC : cycle = {parsed['cycle']} !!!")
    print()
    print("Le texte extrait du PDF doit avoir un format different.")
    print("Affichage des 500 premiers caracteres du texte extrait :")
    print("-" * 60)
    text = parsed.get("raw_text_preview", "")
    print(text[:500])