"""Trouve le code qui gere le matching de langues."""
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
py_files = list(PROJECT_ROOT.rglob("*.py"))
py_files = [f for f in py_files if not any(
    p in str(f) for p in ["venv", "__pycache__", "site-packages", ".git", "cache"]
)]

# Cherche les patterns lies au matching de langues requises
patterns = [
    r"required_languages",
    r"langue\s+requise",
    r"Langue\s+requise",
    r"languages_human",
    r"Francais",
    r"Français",
    r"pillar_languag",
    r"score_languag",
    r"def.*lang",
]

hits = {}
for f in py_files:
    try:
        content = f.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    lines = content.split("\n")
    file_hits = []
    for lineno, line in enumerate(lines, 1):
        for p in patterns:
            if re.search(p, line, re.IGNORECASE):
                file_hits.append((lineno, line.strip()[:140]))
                break
    if file_hits:
        hits[f] = file_hits

for f, h in sorted(hits.items()):
    rel = f.relative_to(PROJECT_ROOT)
    print(f"\n>>> {rel}")
    print("-" * 70)
    for lineno, line in h[:20]:  # max 20 lignes par fichier
        print(f"  L{lineno:4d}  {line}")
    if len(h) > 20:
        print(f"  ... ({len(h) - 20} autres lignes)")