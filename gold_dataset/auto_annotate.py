"""
Script d'annotation automatique — remplit tous les null dans annotations.json
Usage : python gold_dataset/auto_annotate.py

Ce script :
1. Lit annotations.json (ton fichier gold dataset)
2. Pour chaque CV avec des null, extrait les compétences du PDF
3. Calcule le score pour chaque sujet
4. Remplit les null avec ADAPTE / PARTIELLEMENT_ADAPTE / PEU_ADAPTE
5. Sauvegarde le résultat dans annotations_complete.json
"""

import json
import sys
from pathlib import Path

# --- Chemin racine du projet ---
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.core.cv_parser import cv_parser
from app.core.scorer import scorer

# --- Chemins ---
CVS_DIR         = Path(__file__).parent / "cvs"
ANNOTATIONS_IN  = Path(__file__).parent / "annotations.json"
ANNOTATIONS_OUT = Path(__file__).parent / "annotations_complete.json"

# --- Définition des 7 sujets (même structure que StageSubject) ---
# On les recrée ici pour être autonome
from app.models.schemas import StageSubject

# Au début du fichier, après les imports existants :
sys.path.insert(0, str(Path(__file__).parent))
from subjects_loader import load_subjects

# Supprime tout le bloc "SUBJECTS = { 'S1_BACKEND': StageSubject(...), ... }"
# Remplace par cette ligne :
SUBJECTS = load_subjects()


def load_annotations():
    with open(ANNOTATIONS_IN, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["annotations"]


def parse_cv(pdf_path: Path) -> dict | None:
    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        return cv_parser.parse(pdf_bytes)
    except Exception as e:
        print(f"   ❌ Erreur parsing : {e}")
        return None


def annotate_cv(cv_data: dict, current: dict) -> dict:
    """Remplit les null pour un CV donné."""
    updated = dict(current)
    for subject_key, subject in SUBJECTS.items():
        if current.get(subject_key) is None:
            try:
                result = scorer.score(cv_data, subject)
                updated[subject_key] = result.recommendation
            except Exception as e:
                print(f"      ⚠️  Erreur scoring {subject_key} : {e}")
                updated[subject_key] = "PEU_ADAPTE"
    return updated


def main():
    print("=" * 60)
    print("  AUTO-ANNOTATION — Gold Dataset")
    print("=" * 60)

    annotations = load_annotations()
    total = len(annotations)
    updated_count = 0

    results = []
    for i, entry in enumerate(annotations, 1):
        filename = entry["cv_filename"]
        pdf_path = CVS_DIR / filename

        # Vérifie si ce CV a des null à remplir
        has_null = any(v is None for k, v in entry.items() if k != "cv_filename")

        if not has_null:
            print(f"[{i}/{total}] ✅ {filename} — déjà complet")
            results.append(entry)
            continue

        print(f"[{i}/{total}] 🔍 {filename} — annotation en cours...")

        if not pdf_path.exists():
            print(f"   ⚠️  PDF introuvable : {pdf_path}")
            results.append(entry)
            continue

        cv_data = parse_cv(pdf_path)
        if cv_data is None:
            results.append(entry)
            continue

        skills_total = cv_data.get("skills", {}).get("total", 0)
        print(f"   📊 {skills_total} compétences détectées")

        updated_entry = annotate_cv(cv_data, entry)

        # Affiche les nouveaux labels
        for s in ["S4_FULLSTACK", "S5_DATA_IA", "S6_DEVOPS", "S7_RESEAUX"]:
            if entry.get(s) is None:
                print(f"   → {s} : {updated_entry[s]}")

        results.append(updated_entry)
        updated_count += 1

    # Sauvegarde
    output = {
        "version": "3.0-complete",
        "total_cases": sum(
            sum(1 for k, v in r.items() if k != "cv_filename" and v is not None)
            for r in results
        ),
        "annotations": results,
    }

    with open(ANNOTATIONS_OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✅ Terminé ! {updated_count} CVs annotés automatiquement.")
    print(f"💾 Résultat sauvegardé dans : {ANNOTATIONS_OUT}")
    print("="*60)


if __name__ == "__main__":
    main()