"""
find_best_thresholds.py — version corrigée
Utilise exactement le même pipeline qu'evaluate.py
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.core.cv_parser import cv_parser
from app.core.scorer import scorer
from app.models.schemas import StageSubject

# ===== Charger annotations (même source qu'evaluate.py) =====
GOLD_DATASET_DIR = Path(__file__).parent
CVS_DIR          = GOLD_DATASET_DIR / "cvs"
ANNOTATIONS_FILE = GOLD_DATASET_DIR / "annotations.json"

with open(ANNOTATIONS_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

subjects_dict = data["subjects"]   # clé "subjects" dans annotations.json
annotations   = data["annotations"]

# ===== Calculer les VRAIS scores (même pipeline qu'evaluate.py) =====
cases    = []
cv_cache = {}

print("Calcul des vrais scores...")

for ann in annotations:
    cv_filename = ann["cv_filename"]
    cv_path     = CVS_DIR / cv_filename

    if not cv_path.exists():
        print(f"  ⚠️  {cv_filename} introuvable")
        continue

    # Parse le CV en bytes — exactement comme evaluate.py
    if cv_filename not in cv_cache:
        try:
            with open(cv_path, "rb") as f:
                cv_cache[cv_filename] = cv_parser.parse(f.read())
        except Exception as e:
            print(f"  ❌ Parsing {cv_filename} : {e}")
            continue

    cv_data = cv_cache[cv_filename]

    for subj_id, subj_def in subjects_dict.items():
        label_human = ann.get(subj_id)
        if not label_human:
            continue

        subject = StageSubject(**subj_def)

        try:
            result = scorer.score(cv_data, subject)
            cases.append({
                "cv":      cv_filename,
                "subject": subj_id,
                "label":   label_human,
                "score":   result.final_score,
            })
        except Exception as e:
            print(f"  ❌ Scoring {cv_filename}/{subj_id} : {e}")

print(f"\n{len(cases)} cas calculés\n")

if not cases:
    print("❌ Aucun cas — vérifie les CVs et annotations.json")
    sys.exit(1)

# ===== Distribution des scores par label =====
score_by_label = defaultdict(list)
for c in cases:
    score_by_label[c["label"]].append(c["score"])

print("Distribution des scores par label humain :")
for label in ["ADAPTE", "PARTIELLEMENT_ADAPTE", "PEU_ADAPTE"]:
    scores = sorted(score_by_label.get(label, []))
    if not scores:
        continue
    avg = sum(scores) / len(scores)
    print(f"  {label:30s} : n={len(scores):2d} | min={min(scores):.1f} | avg={avg:.1f} | max={max(scores):.1f}")

print()

# ===== Recherche exhaustive des meilleurs seuils =====
best_acc        = 0
best_thresholds = (0, 0)

for t1 in range(40, 85):
    for t2 in range(t1 + 3, 98):
        correct = sum(
            1 for c in cases
            if (
                ("ADAPTE" if c["score"] >= t2
                 else "PARTIELLEMENT_ADAPTE" if c["score"] >= t1
                 else "PEU_ADAPTE")
                == c["label"]
            )
        )
        acc = correct / len(cases)
        if acc > best_acc:
            best_acc        = acc
            best_thresholds = (t1, t2)

t1, t2 = best_thresholds
print("===== RÉSULTAT =====")
print(f"Best t1 (PARTIEL) : {t1}")
print(f"Best t2 (ADAPTE)  : {t2}")
print(f"Best accuracy     : {round(best_acc * 100, 2)} %")
print()
print("👉 Dans scorer.py, mets :")
print(f"   THRESHOLD_ADAPTE        = {t2}")
print(f"   THRESHOLD_PARTIELLEMENT = {t1}")

# ===== Matrice de confusion =====
labels = ["ADAPTE", "PARTIELLEMENT_ADAPTE", "PEU_ADAPTE"]
matrix = defaultdict(lambda: defaultdict(int))

for c in cases:
    pred = ("ADAPTE" if c["score"] >= t2
            else "PARTIELLEMENT_ADAPTE" if c["score"] >= t1
            else "PEU_ADAPTE")
    matrix[c["label"]][pred] += 1

print("\nMatrice de confusion :")
col_title = "Humain / IA"
header = f"{col_title:28s}" + "".join(f"{l[:14]:>16s}" for l in labels)
print(header)
for true_label in labels:
    row = f"  {true_label[:26]:26s}" + "".join(f"{matrix[true_label][pred]:>16d}" for pred in labels)
    print(row)