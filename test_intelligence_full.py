"""
Test direct sur le pipeline complet de cv_intelligence.py
Place a la racine du projet et lance.
"""
import sys
import inspect
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core import cv_intelligence as ci_module
from app.core.cv_intelligence import (
    _aggressive_normalize,
    _regex_detect_cycle,
    _detect_cycle_from_timeline,
    extract_intelligent_info,
    clear_cache,
)
from app.core.cv_parser import cv_parser
from app.core.ner_extractor import ner_extractor

print("=" * 70)
print("ETAPE 1 : Verifier la version de cv_intelligence.py")
print("=" * 70)
source = inspect.getsource(ci_module)
if "v11.0" in source[:500]:
    print("OK : cv_intelligence.py est en v11.0")
else:
    print("!!! cv_intelligence.py N'EST PAS en v11.0 !!!")
    print("Premier docstring :")
    print(source[:300])
    sys.exit(1)

print()
print("=" * 70)
print("ETAPE 2 : Vider le cache")
print("=" * 70)
clear_cache()

print()
print("=" * 70)
print("ETAPE 3 : Parser le CV puis envoyer a cv_intelligence")
print("=" * 70)
CV_PATH = r"C:\Users\ousse\Downloads\AI-main\AI-main\gold_dataset\cvs\CV_Ahmed_benAli.pdf"

parsed = cv_parser.parse(CV_PATH)
text = parsed["raw_text_preview"]  # texte anonymise (utilise en aval)
orgs = parsed["ner"]["organizations"]

print(f"Cycle d'apres cv_parser.parse() : {parsed['cycle']}")
print(f"Longueur texte anonymise : {len(text)}")
print(f"Nombre d'organisations : {len(orgs)}")

print()
print("=" * 70)
print("ETAPE 4 : Tester _detect_cycle_from_timeline sur le VRAI texte")
print("=" * 70)
text_norm = _aggressive_normalize(text)
print(f"500 premiers caracteres du texte normalise :")
print("-" * 60)
print(text_norm[:500])
print("-" * 60)

timeline = _detect_cycle_from_timeline(text_norm)
print(f"\nResultat timeline : {timeline}")

print()
print("=" * 70)
print("ETAPE 5 : Tester _regex_detect_cycle complet")
print("=" * 70)
result = _regex_detect_cycle(text_norm)
print(f"Resultat : {result}")

print()
print("=" * 70)
print("ETAPE 6 : Pipeline complet extract_intelligent_info")
print("=" * 70)
info = extract_intelligent_info(text, orgs, use_llm=True)
print(f"Cycle consensus final : {info['cycle']}")
print(f"_cycle_source : {info.get('_cycle_source')}")
print(f"LLM utilise : {info['_llm_used']}")
if info.get("_raw_llm_result"):
    print(f"LLM dit : cycle={info['_raw_llm_result'].get('cycle')}, "
          f"annee={info['_raw_llm_result'].get('annee_etude')}")

print()
print("=" * 70)
print("VERDICT FINAL")
print("=" * 70)
if info['cycle']['value'] == 'master':
    print("*** SUCCES : pipeline complet retourne master ***")
elif info['cycle']['value'] == 'licence':
    print("*** ECHEC : pipeline retourne licence ***")
    print()
    print("Diagnostic :")
    if not timeline:
        print("  - La timeline n'a rien trouve dans le texte anonymise du PDF")
        print("  - Il faut regarder le texte ci-dessus (etape 4) pour voir")
        print("    comment les dates sont formatees apres anonymisation")
    if info.get("_raw_llm_result", {}).get("cycle") == "licence":
        print("  - Le LLM lui-meme dit 'licence' !")
        print("  - Il faut ajuster le prompt LLM dans llm_cv_extractor.py")