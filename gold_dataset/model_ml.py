"""
Modèle ML de classification CV → label
Remplace les thresholds fixes par une Logistic Regression
entraînée sur les vrais scores du gold dataset
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.core.cv_parser import cv_parser
from app.core.scorer import scorer, CompatibilityScorer
from app.models.schemas import StageSubject
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import cross_val_score
import numpy as np

GOLD_DATASET_DIR = Path(__file__).parent
CVS_DIR          = GOLD_DATASET_DIR / "cvs"
ANNOTATIONS_FILE = GOLD_DATASET_DIR / "annotations.json"

with open(ANNOTATIONS_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

subjects_dict = data["subjects"]
annotations   = data["annotations"]

# ===== Extraire les features =====
X = []
y = []
cv_cache = {}

print("Extraction des features...")

for ann in annotations:
    cv_filename = ann["cv_filename"]
    cv_path     = CVS_DIR / cv_filename
    if not cv_path.exists():
        continue

    if cv_filename not in cv_cache:
        try:
            with open(cv_path, "rb") as f:
                cv_cache[cv_filename] = cv_parser.parse(f.read())
        except:
            continue

    cv_data = cv_cache[cv_filename]

    for subj_id, subj_def in subjects_dict.items():
        label_human = ann.get(subj_id)
        if not label_human:
            continue

        subject = StageSubject(**subj_def)

        try:
            result = scorer.score(cv_data, subject)
            p = result.pillars

            # Features : tous les piliers + score final + skills_count
            skills_count = cv_data.get("skills", {}).get("total", 0)
            features = [
                result.final_score,
                p["skills"].score,
                p["formation"].score,
                p["experience"].score,
                p["soft_skills"].score,
                p["languages"].score,
                p["motivation"].score,
                skills_count,
                result.semantic_similarity,
            ]
            X.append(features)
            y.append(label_human)
        except Exception as e:
            print(f"  Erreur {cv_filename}/{subj_id}: {e}")

print(f"{len(X)} cas extraits")

X = np.array(X)
labels = ["ADAPTE", "PARTIELLEMENT_ADAPTE", "PEU_ADAPTE"]
le = LabelEncoder()
le.fit(labels)
y_enc = le.transform(y)

# ===== Entraîner le modèle =====
model = LogisticRegression(
    C=0.5,
    max_iter=1000,
    class_weight="balanced",
    random_state=42,
    multi_class="multinomial",
)

# Cross-validation leave-one-out
from sklearn.model_selection import LeaveOneOut
loo = LeaveOneOut()
scores = cross_val_score(model, X, y_enc, cv=loo, scoring="accuracy")

print(f"\n===== RÉSULTAT ML =====")
print(f"Accuracy LOO : {scores.mean()*100:.1f}%")
print(f"(vs thresholds fixes : ~63.5%)")

# Matrice de confusion LOO
from sklearn.model_selection import cross_val_predict
from sklearn.metrics import confusion_matrix, f1_score, cohen_kappa_score

y_pred_enc = cross_val_predict(model, X, y_enc, cv=loo)
y_pred = le.inverse_transform(y_pred_enc)

print(f"\nF1 macro  : {f1_score(y, y_pred, labels=labels, average='macro', zero_division=0):.3f}")
print(f"Kappa     : {cohen_kappa_score(y, y_pred, labels=labels):.3f}")

print("\nMatrice de confusion :")
cm = confusion_matrix(y, y_pred, labels=labels)
col_title = "Humain / IA"
header = f"{col_title:28s}" + "".join(f"{l[:14]:>18s}" for l in labels)
print(header)
for i, true_label in enumerate(labels):
    row = f"  {true_label[:26]:26s}" + "".join(f"{cm[i][j]:>18d}" for j in range(len(labels)))
    print(row)

# ===== Sauvegarder le modèle entraîné sur TOUT le dataset =====
from sklearn.preprocessing import StandardScaler
import pickle

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

model.fit(X_scaled, y_enc)

model_data = {
    "model": model,
    "scaler": scaler,
    "label_encoder": le,
}

with open(GOLD_DATASET_DIR / "ml_classifier.pkl", "wb") as f:
    pickle.dump(model_data, f)

print("\n✅ Modèle sauvegardé : ml_classifier.pkl")