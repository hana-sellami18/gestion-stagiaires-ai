"""
Debug script — a placer a la racine du projet AI (au meme niveau que app/)
Usage : python debug_ahmed.py
"""
import sys
from pathlib import Path

# Ajuste le path si necessaire
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core import cv_parser
from app.core.cv_intelligence import (
    _aggressive_normalize,
    _extract_formation_section,
    _detect_cycle_from_timeline,
    _regex_detect_cycle,
    _llm_cache,
    clear_cache,
)
import hashlib

# ============================================================
# CONFIGURE LE CHEMIN DU CV ICI
# ============================================================
CV_PATH = "C:\ousse\Downloads\AI-main\AI-main\gold_dataset\cvs\CV_Ahmed_benAli.pdf"  # <-- AJUSTE CE CHEMIN

print("=" * 70)
print("ETAPE 1 : Verifier la version du module")
print("=" * 70)
import app.core.cv_intelligence as ci
import inspect
source_first_lines = inspect.getsource(ci).split("\n")[:5]
for line in source_first_lines:
    print(line)

if "v11.0" not in inspect.getsource(ci)[:1000]:
    print("\n!!! ATTENTION : tu n'utilises PAS la v11.0 !!!")
    print("Le fichier cv_intelligence.py n'a pas ete remplace correctement.")
    sys.exit(1)
else:
    print("\nOK : v11.0 detectee")

print("\n" + "=" * 70)
print("ETAPE 2 : Vider le cache LLM")
print("=" * 70)
clear_cache()
print(f"Cache vide. Taille actuelle : {len(_llm_cache)}")

print("\n" + "=" * 70)
print("ETAPE 3 : Parser le CV")
print("=" * 70)
parsed = cv_parser.parse_cv("C:\ousse\Downloads\AI-main\AI-main\gold_dataset\cvs\CV_Ahmed_benAli.pdf")
cv_text = parsed.get("text", "") or parsed.get("raw_text", "")
print(f"Longueur texte brut : {len(cv_text)} caracteres")
print(f"\n--- DEBUT DU TEXTE BRUT (200 premiers caracteres) ---")
print(cv_text[:200])
print("--- FIN DEBUT ---\n")

print("=" * 70)
print("ETAPE 4 : Texte normalise")
print("=" * 70)
text_norm = _aggressive_normalize(cv_text)
print(f"Longueur apres normalisation : {len(text_norm)}")

print("\n" + "=" * 70)
print("ETAPE 5 : Section Formation extraite")
print("=" * 70)
formation = _extract_formation_section(text_norm)
if not formation:
    print("!!! SECTION FORMATION NON DETECTEE !!!")
    print("La regex de _extract_formation_section ne matche pas le format du CV.")
    print("\nCherche manuellement 'Master' dans le texte :")
    import re
    for m in re.finditer(r".{50}(master|licence|baccalaur).{50}", text_norm, re.IGNORECASE):
        print(f"  ...{m.group()}...")
else:
    print(f"Longueur section Formation : {len(formation)}")
    print("--- DEBUT SECTION FORMATION ---")
    print(formation[:800])
    print("--- FIN ---")

print("\n" + "=" * 70)
print("ETAPE 6 : Timeline detection")
print("=" * 70)
timeline = _detect_cycle_from_timeline(text_norm)
if timeline:
    print(f"Cycle detecte : {timeline['cycle']}")
    print(f"Source        : {timeline['source']}")
    print(f"Evidence      : {timeline['evidence']}")
else:
    print("!!! TIMELINE N'A RIEN TROUVE !!!")
    print("Soit pas de dates parsables, soit format inattendu.")

print("\n" + "=" * 70)
print("ETAPE 7 : _regex_detect_cycle complet")
print("=" * 70)
result = _regex_detect_cycle(text_norm)
print(f"Resultat final : {result}")

if result["cycle"] == "master":
    print("\n*** SUCCES : cycle detecte = master ***")
elif result["cycle"] == "licence":
    print("\n*** ECHEC : cycle detecte = licence ***")
    print("Probleme dans la section Formation ou la regex de dates.")
else:
    print(f"\n*** Cycle inattendu : {result['cycle']} ***")