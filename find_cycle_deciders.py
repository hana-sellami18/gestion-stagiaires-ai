"""
Cherche TOUS les endroits qui decident du cycle final.
Place a la racine du projet et lance : python find_cycle_deciders.py
"""
import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# Patterns qui indiquent une decision sur le cycle
patterns = [
    (r'cycle\s*=\s*["\']licence', "Force cycle a 'licence'"),
    (r'cycle\s*=\s*["\']master', "Force cycle a 'master'"),
    (r'\.cycle\s*=', "Assigne cycle a quelque chose"),
    (r'cycle["\']?\s*:\s*["\']licence', "Dict avec cycle: licence"),
    (r'cycle_consensus\[["\']value["\']\]\s*=', "Modifie cycle_consensus"),
    (r'OVERRIDE.*[Cc]ycle', "Override metier sur cycle"),
    (r'def\s+\w*[Dd]etect_?[Cc]ycle', "Fonction de detection cycle"),
    (r'def\s+\w*[Cc]ycle\w*', "Fonction liee au cycle"),
]

print("=" * 70)
print("RECHERCHE DES DETECTEURS DE CYCLE DANS LE PROJET")
print("=" * 70)

py_files = list(PROJECT_ROOT.rglob("*.py"))
# Exclure venv, __pycache__, etc.
py_files = [f for f in py_files if not any(
    p in str(f) for p in ["venv", "__pycache__", "site-packages", ".git", "cache"]
)]

print(f"Fichiers Python scannes : {len(py_files)}")
print()

hits_by_file = {}
for f in py_files:
    try:
        content = f.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    lines = content.split("\n")
    file_hits = []
    for lineno, line in enumerate(lines, 1):
        for pattern, desc in patterns:
            if re.search(pattern, line):
                file_hits.append((lineno, line.strip()[:120], desc))
                break
    if file_hits:
        hits_by_file[f] = file_hits

# Affiche par fichier
for f, hits in sorted(hits_by_file.items()):
    rel = f.relative_to(PROJECT_ROOT)
    print(f"\n>>> {rel}")
    print("-" * 70)
    for lineno, line, desc in hits:
        print(f"  L{lineno:4d}  [{desc}]")
        print(f"         {line}")

print()
print("=" * 70)
print("RESUME : fichiers a regarder pour comprendre qui ecrase le cycle")
print("=" * 70)
for f in sorted(hits_by_file.keys()):
    print(f"  - {f.relative_to(PROJECT_ROOT)} ({len(hits_by_file[f])} matches)")