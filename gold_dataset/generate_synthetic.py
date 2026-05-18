"""
generate_synthetic.py — version corrigée
Lit extractions.json + annotations.json, rescorer chaque CV,
extrait les features réelles, génère 300 synthétiques, réentraîne.
"""

import json
import pickle
import sys
import numpy as np
from pathlib import Path

# Ajouter le dossier parent au path pour importer app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.scorer import scorer
from app.models.schemas import StageSubject
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import accuracy_score, f1_score, cohen_kappa_score, confusion_matrix

BASE         = Path(__file__).parent
EXTRACTIONS  = BASE / "extractions.json"
ANNOTATIONS  = BASE / "annotations.json"
PKL_PATH     = BASE / "ml_classifier.pkl"
CVS_DIR      = BASE / "cvs"

# ---------------------------------------------------------------------------
# 1. Charger données
# ---------------------------------------------------------------------------
print("Chargement...")
with open(EXTRACTIONS,  "r", encoding="utf-8") as f:
    ext_data = json.load(f)
with open(ANNOTATIONS,  "r", encoding="utf-8") as f:
    ann_data = json.load(f)

subjects_raw = ann_data["subjects"]
cases = ann_data["annotations"]

# Index extractions par filename
ext_index = {r["filename"]: r for r in ext_data["results"]}

# Reconstruire les StageSubject
def make_subject(sid, sd):
    return StageSubject(
        id=sid,
        title=sd["title"],
        description=sd.get("description", ""),
        filiere=sd.get("filiere", "informatique"),
        cycle=sd.get("cycle", "ingénieur"),
        core_skills=sd.get("core_skills", []),
        important_skills=sd.get("important_skills", []),
        bonus_skills=sd.get("bonus_skills", []),
        skill_equivalents=sd.get("skill_equivalents", {}),
        required_languages=sd.get("required_languages", []),
    )

subjects = {sid: make_subject(sid, sd) for sid, sd in subjects_raw.items()}

# ---------------------------------------------------------------------------
# 2. Scorer chaque CV × sujet → extraire features
# ---------------------------------------------------------------------------
print("Scoring des 63 cas réels...")
real_features = []
real_labels   = []

for case in cases:
    filename = case["cv_filename"]
    ext = ext_index.get(filename)
    if not ext:
        print(f"  ⚠️  {filename} non trouvé dans extractions")
        continue

    # Reconstruire cv_data minimal
    ner = ext.get("ner", {})
    cv_data = {
        "skills": ext.get("skills", {}),
        "ner":    ner,
        "raw_text_preview": ext.get("raw_text_preview", ""),
    }

    for sid, subject in subjects.items():
        human_label = case.get(sid)
        if not human_label:
            continue

        try:
            result = scorer.score(cv_data, subject)
            feat = [
                result.final_score,
                result.pillars["skills"].score,
                result.pillars["formation"].score,
                result.pillars["experience"].score,
                result.pillars["soft_skills"].score,
                result.pillars["languages"].score,
                result.pillars["motivation"].score,
                cv_data.get("skills", {}).get("total", len(cv_data.get("skills", {}).get("found_skills", []))),
                result.semantic_similarity,
            ]
            real_features.append(feat)
            real_labels.append(human_label)
        except Exception as e:
            print(f"  ⚠️  Erreur {filename}/{sid}: {e}")

real_features = np.array(real_features)
real_labels   = np.array(real_labels)
print(f"  {len(real_labels)} cas réels scorés")

# Distribution par classe
classes = ["ADAPTE", "PARTIELLEMENT_ADAPTE", "PEU_ADAPTE"]
distributions = {}
for cls in classes:
    mask = real_labels == cls
    data = real_features[mask]
    distributions[cls] = {
        "mean": data.mean(axis=0),
        "std":  np.maximum(data.std(axis=0), 2.0),
        "count": len(data)
    }
    print(f"  {cls}: {len(data)} cas, score moyen={data[:,0].mean():.1f}")

# ---------------------------------------------------------------------------
# 3. Générer 300 samples synthétiques
# ---------------------------------------------------------------------------
N_PER_CLASS = 100
BOUNDS = [
    (0, 100), (0, 100), (0, 80), (0, 100),
    (0, 100), (0, 100), (0, 100), (0, 50), (0, 1),
]

# Seuils de cohérence par classe
SCORE_BOUNDS = {
    "ADAPTE":               (72, 100),
    "PARTIELLEMENT_ADAPTE": (52, 84),
    "PEU_ADAPTE":           (0,  70),
}

print(f"\nGénération de {N_PER_CLASS * 3} samples synthétiques...")
syn_features = []
syn_labels   = []
np.random.seed(42)

for cls in classes:
    d = distributions[cls]
    lo_score, hi_score = SCORE_BOUNDS[cls]
    generated = 0
    attempts  = 0

    while generated < N_PER_CLASS and attempts < 5000:
        attempts += 1
        sample = np.random.normal(d["mean"], d["std"])
        for i, (lo, hi) in enumerate(BOUNDS):
            sample[i] = np.clip(sample[i], lo, hi)
        sample[7] = round(sample[7])

        if not (lo_score <= sample[0] <= hi_score):
            continue

        syn_features.append(sample)
        syn_labels.append(cls)
        generated += 1

    print(f"  {cls}: {generated} générés en {attempts} tentatives")

syn_features = np.array(syn_features)
syn_labels   = np.array(syn_labels)

# ---------------------------------------------------------------------------
# 4. Mixer + réentraîner
# ---------------------------------------------------------------------------
X_train = np.vstack([real_features, syn_features])
y_train = np.concatenate([real_labels, syn_labels])
print(f"\nEntraînement sur {len(y_train)} cas ({len(real_labels)} réels + {len(syn_labels)} synthétiques)")

le      = LabelEncoder()
y_enc   = le.fit_transform(y_train)
scaler  = StandardScaler()
X_sc    = scaler.fit_transform(X_train)
model   = LogisticRegression(max_iter=5000, random_state=42)
model.fit(X_sc, y_enc)

# ---------------------------------------------------------------------------
# 5. Évaluer sur les 63 réels UNIQUEMENT
# ---------------------------------------------------------------------------
print("\nÉvaluation sur les 63 cas réels uniquement...")
X_real_sc  = scaler.transform(real_features)
y_real_enc = le.transform(real_labels)
y_pred_enc = model.predict(X_real_sc)
y_pred     = le.inverse_transform(y_pred_enc)

acc   = accuracy_score(real_labels, y_pred)
f1    = f1_score(real_labels, y_pred, average="macro", zero_division=0)
kappa = cohen_kappa_score(real_labels, y_pred)
cm    = confusion_matrix(real_labels, y_pred, labels=classes)

print(f"""
===== RÉSULTAT APRÈS AUGMENTATION =====
  Entraînement : {len(y_train)} cas
  Évaluation   : {len(real_labels)} cas réels

  Accuracy : {acc*100:.1f}%
  F1 macro : {f1:.3f}
  Kappa    : {kappa:.3f}

Matrice de confusion :
{'Humain/IA':<25} {'ADAPTE':>10} {'PARTIELLEMENT':>15} {'PEU_ADAPTE':>12}""")

for i, row in enumerate(classes):
    print(f"  {row:<25} {cm[i][0]:>10} {cm[i][1]:>15} {cm[i][2]:>12}")

# ---------------------------------------------------------------------------
# 6. Sauvegarder
# ---------------------------------------------------------------------------
md = {"model": model, "scaler": scaler, "label_encoder": le}
with open(PKL_PATH, "wb") as f:
    pickle.dump(md, f)

print(f"\n✅ Modèle sauvegardé : {PKL_PATH}")
print("Lance : python evaluate.py pour confirmer sur gold dataset.")