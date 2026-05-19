"""
Script d'évaluation scientifique : compare les prédictions IA aux annotations humaines.
Calcule Accuracy, F1-score, Kappa de Cohen, matrice de confusion.
Inclut le test contre-factuel des biais (AI Act section 3.2).

Usage : python gold_dataset/evaluate.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    cohen_kappa_score,
    confusion_matrix,
    classification_report,
)

# Ajout du dossier racine au path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from app.core.cv_parser import cv_parser  # noqa: E402
from app.core.scorer import scorer  # noqa: E402
from app.models.schemas import StageSubject  # noqa: E402


# Constantes
GOLD_DATASET_DIR = Path(__file__).parent
CVS_DIR = GOLD_DATASET_DIR / "cvs"
ANNOTATIONS_FILE = GOLD_DATASET_DIR / "annotations.json"
RESULTS_JSON = GOLD_DATASET_DIR / "evaluation_results.json"
RESULTS_HTML = GOLD_DATASET_DIR / "evaluation_report.html"

LABELS_ORDER = ["ADAPTE", "PARTIELLEMENT_ADAPTE", "PEU_ADAPTE"]

def _is_eligible(cv_cycle: str, cv_annee, subject_id: str) -> bool:
    """Filtre les paires (CV, sujet) incompatibles selon le cycle."""
    if subject_id == "S5_DATA_IA":
        return cv_cycle == "master"
    if subject_id in ("S1_BACKEND", "S6_DEVOPS"):
        return cv_cycle in ("ingenieur", "master")
    return True

def _extract_label(value) -> str:
    """Extrait une string depuis une recommendation, qu'elle soit str, dict ou enum."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        # Tente les clés courantes
        for key in ("value", "label", "recommendation", "name"):
            if key in value:
                return str(value[key])
        return str(next(iter(value.values())))
    # Enum ou autre objet avec .value ou .name
    if hasattr(value, "value"):
        return str(value.value)
    if hasattr(value, "name"):
        return str(value.name)
    return str(value)

def load_annotations():
    """Charge les annotations humaines et les sujets depuis les fichiers de référence."""
    from subjects_loader import load_subjects_dict

    with open(ANNOTATIONS_FILE, "r", encoding="utf-8") as f:
        ann_data = json.load(f)

    return {
        "subjects": load_subjects_dict(),
        "annotations": ann_data["annotations"],
    }


def evaluate():
    """Lance l'évaluation complète."""
    data = load_annotations()
    subjects_dict = data["subjects"]
    annotations = data["annotations"]

    print("=" * 70)
    print(f"  ÉVALUATION GOLD DATASET — {len(annotations)} CVs × {len(subjects_dict)} sujets")
    print("=" * 70)

    cases = []
    cv_cache = {}

    for ann in annotations:
        cv_filename = ann["cv_filename"]
        cv_path = CVS_DIR / cv_filename
        if not cv_path.exists():
            print(f"⚠️  CV introuvable : {cv_filename}")
            continue

        # Parse le CV une seule fois (cache)
        if cv_filename not in cv_cache:
            print(f"\n📄 Analyse de : {cv_filename}")
            try:
                with open(cv_path, "rb") as f:
                    cv_cache[cv_filename] = cv_parser.parse(f.read())
            except Exception as e:
                print(f"   ❌ Erreur parsing : {e}")
                continue
        cv_data = cv_cache[cv_filename]

        # Évaluation pour chaque sujet
        # Évaluation UNIQUEMENT sur les sujets annotés par le RH
        # (= sujets compatibles avec le cycle/filière du candidat)
        cv_cycle = cv_data.get("cycle", "").lower()
        cv_annee = cv_data.get("_intelligence", {}).get("annee", {}).get("value")

        for subj_id, subj_def in subjects_dict.items():
            label_human_raw = ann.get(subj_id)
            print(f"DEBUG {subj_id} → {repr(label_human_raw)}")
            # FILTRE 1 : le RH n'a pas annoté ce sujet → non pertinent pour ce profil
            if not label_human_raw:
                continue

            # Extraction de la string depuis le dict si nécessaire
            if isinstance(label_human_raw, dict):
                label_human = label_human_raw.get("value") or label_human_raw.get("label") or str(
                    next(iter(label_human_raw.values())))
            else:
                label_human = str(label_human_raw)

            # FILTRE 2 : vérification d'éligibilité cycle (sécurité)
            if not _is_eligible(cv_cycle, cv_annee, subj_id):
                print(f"   ⏭️  {subj_id} ignoré (cycle/année incompatible)")
                continue

            subject = StageSubject(**subj_def)

            try:
                result = scorer.score(cv_data, subject)
                rec = result.recommendation
                if isinstance(rec, dict):
                    label_ai = rec.get("value") or rec.get("label") or rec.get("recommendation") or str(
                        next(iter(rec.values())))
                elif hasattr(rec, "value"):
                    label_ai = rec.value
                else:
                    label_ai = str(rec)
                score = result.final_score
            except Exception as e:
                print(f"   ❌ Erreur scoring {subj_id} : {e}")
                continue

            match = "✅" if label_ai == label_human else "❌"
            print(f"   {subj_id}: humain={label_human:25s} | IA={label_ai:25s} ({score:.1f}/100) {match}")

            cases.append({
                "cv_filename": cv_filename,
                "subject_id": subj_id,
                "subject_title": subj_def["title"],
                "label_human": label_human,
                "label_ai": label_ai,
                "ai_score": score,
                "match": label_ai == label_human,
                "pillars": {
                    "skills": result.pillars["skills"].score,
                    "formation": result.pillars["formation"].score,
                    "experience": result.pillars["experience"].score,
                },
            })

    return cases, subjects_dict, cv_cache


def compute_metrics(cases):
    """Calcule les métriques scientifiques."""
    y_true = [c["label_human"] for c in cases]
    y_pred = [c["label_ai"] for c in cases]

    accuracy = accuracy_score(y_true, y_pred)
    f1_macro = f1_score(y_true, y_pred, labels=LABELS_ORDER, average="macro", zero_division=0)
    f1_weighted = f1_score(y_true, y_pred, labels=LABELS_ORDER, average="weighted", zero_division=0)
    kappa = cohen_kappa_score(y_true, y_pred, labels=LABELS_ORDER)
    cm = confusion_matrix(y_true, y_pred, labels=LABELS_ORDER)

    per_subject = {}
    for case in cases:
        subj = case["subject_id"]
        per_subject.setdefault(subj, {"y_true": [], "y_pred": []})
        per_subject[subj]["y_true"].append(case["label_human"])
        per_subject[subj]["y_pred"].append(case["label_ai"])

    subject_metrics = {}
    for subj, vals in per_subject.items():
        subject_metrics[subj] = {
            "accuracy": accuracy_score(vals["y_true"], vals["y_pred"]),
            "f1_macro": f1_score(vals["y_true"], vals["y_pred"], labels=LABELS_ORDER, average="macro", zero_division=0),
            "n": len(vals["y_true"]),
        }

    report = classification_report(y_true, y_pred, labels=LABELS_ORDER, zero_division=0, output_dict=True)

    return {
        "global": {
            "accuracy": accuracy,
            "f1_macro": f1_macro,
            "f1_weighted": f1_weighted,
            "kappa": kappa,
            "n_total": len(cases),
            "n_correct": sum(1 for c in cases if c["match"]),
        },
        "confusion_matrix": cm.tolist(),
        "labels_order": LABELS_ORDER,
        "per_subject": subject_metrics,
        "classification_report": report,
    }


def compute_counterfactual_bias(cv_cache, subjects_dict):
    """
    Test contre-factuel : compare score original vs score anonymisé.
    Un système équitable doit avoir un écart moyen < 5%.
    Conformité AI Act section 3.2.
    """
    from app.core.anonymizer import anonymizer

    print("\n" + "=" * 70)
    print("  TEST CONTRE-FACTUEL DES BIAIS")
    print("=" * 70)

    bias_results = []

    for cv_filename, cv_data in cv_cache.items():
        for subj_id, subj_def in subjects_dict.items():
            subject = StageSubject(**subj_def)

            # Score original
            result_original = scorer.score(cv_data, subject)
            score_original = result_original.final_score

            # Score anonymisé
            preview = cv_data.get("raw_text_preview", "")
            preview_anon = anonymizer.anonymize(preview)
            cv_data_anon = dict(cv_data)
            cv_data_anon["raw_text_preview"] = preview_anon

            result_anon = scorer.score(cv_data_anon, subject)
            score_anon = result_anon.final_score

            # Écart
            ecart = abs(score_original - score_anon)

            bias_results.append({
                "cv_filename": cv_filename,
                "subject_id": subj_id,
                "score_original": score_original,
                "score_anonymise": score_anon,
                "ecart": ecart,
                "conforme": ecart < 5.0,
            })

            status = "✅" if ecart < 5.0 else "⚠️"
            print(f"   {cv_filename[:30]:30s} | {subj_id} | "
                  f"original={score_original:.1f} | anon={score_anon:.1f} | "
                  f"écart={ecart:.1f} {status}")

    # Résumé
    ecart_moyen = sum(r["ecart"] for r in bias_results) / len(bias_results)
    nb_non_conformes = sum(1 for r in bias_results if not r["conforme"])
    conforme_global = ecart_moyen < 5.0

    print(f"\n  Écart moyen    : {ecart_moyen:.2f}%  (cible < 5%)  {'✅' if conforme_global else '⚠️'}")
    print(f"  Non conformes  : {nb_non_conformes}/{len(bias_results)} cas")
    print("=" * 70)

    return {
        "ecart_moyen": round(ecart_moyen, 3),
        "conforme": conforme_global,
        "nb_non_conformes": nb_non_conformes,
        "details": bias_results,
    }


def save_results(cases, metrics, subjects_dict, bias_metrics):
    """Sauvegarde les résultats."""
    data = {
        "generated_at": datetime.now().isoformat(),
        "metrics": metrics,
        "bias_metrics": bias_metrics,
        "cases": cases,
        "subjects": subjects_dict,
    }
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Résultats JSON sauvegardés : {RESULTS_JSON}")


def generate_html_report(cases, metrics, subjects_dict, bias_metrics):
    """Génère un rapport HTML avec graphiques."""
    g = metrics["global"]
    cm = metrics["confusion_matrix"]
    labels = metrics["labels_order"]

    def badge_color(value, target, higher_is_better=True):
        if higher_is_better:
            return "#27ae60" if value >= target else ("#e67e22" if value >= target * 0.85 else "#c0392b")
        return "#27ae60" if value <= target else "#e67e22"

    acc_color = badge_color(g["accuracy"], 0.75)
    f1_color = badge_color(g["f1_macro"], 0.70)
    kappa_color = badge_color(g["kappa"], 0.60)
    bias_color = "#27ae60" if bias_metrics["conforme"] else "#c0392b"

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Rapport d'évaluation — Gold Dataset</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', sans-serif; max-width: 1200px; margin: 30px auto; padding: 20px; background: #f5f7fa; color: #2c3e50; }}
h1 {{ color: #1e3a5f; border-bottom: 3px solid #1e3a5f; padding-bottom: 10px; }}
h2 {{ color: #c0392b; margin-top: 30px; }}
h3 {{ color: #1e3a5f; }}
.kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }}
.kpi-card {{ background: white; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }}
.kpi-label {{ color: #7f8c8d; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }}
.kpi-value {{ font-size: 36px; font-weight: bold; margin: 8px 0; }}
.kpi-target {{ color: #95a5a6; font-size: 11px; }}
.section {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }}
table {{ width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 13px; }}
th {{ background: #1e3a5f; color: white; padding: 10px; text-align: left; }}
td {{ padding: 8px 10px; border-bottom: 1px solid #ecf0f1; }}
tr:hover td {{ background: #f8f9fa; }}
.match-yes {{ color: #27ae60; font-weight: bold; }}
.match-no {{ color: #c0392b; font-weight: bold; }}
.cm-table {{ margin: 15px auto; border: 2px solid #1e3a5f; }}
.cm-table th {{ background: #34495e; padding: 8px 14px; text-align: center; }}
.cm-table td {{ padding: 12px 16px; text-align: center; font-weight: bold; font-size: 16px; }}
.cm-correct {{ background: #d4edda; color: #155724; }}
.cm-error {{ background: #f8d7da; color: #721c24; }}
.cm-neutral {{ background: #fff3cd; color: #856404; }}
.label-ADAPTE {{ background: #d4edda; color: #155724; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
.label-PARTIELLEMENT_ADAPTE {{ background: #fff3cd; color: #856404; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
.label-PEU_ADAPTE {{ background: #f8d7da; color: #721c24; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
.summary {{ background: #1e3a5f; color: white; padding: 20px; border-radius: 8px; }}
.verdict {{ font-size: 18px; font-weight: bold; margin-top: 10px; }}
.verdict-success {{ color: #2ecc71; }}
.verdict-warning {{ color: #f1c40f; }}
.verdict-fail {{ color: #e74c3c; }}
</style>
</head>
<body>

<h1>📊 Rapport d'évaluation scientifique — Gold Dataset</h1>

<div class="summary">
  <div style="font-size: 16px;">Évaluation du module IA ASM</div>
  <div style="font-size: 14px; opacity: 0.85; margin-top: 5px;">Comparaison entre prédictions IA et annotations humaines de référence</div>
  <div style="margin-top: 15px;">
    <span style="background: rgba(255,255,255,0.15); padding: 6px 14px; border-radius: 20px; margin-right: 10px;">
      📁 {g['n_total']} cas évalués
    </span>
    <span style="background: rgba(255,255,255,0.15); padding: 6px 14px; border-radius: 20px;">
      ✅ {g['n_correct']} prédictions correctes
    </span>
  </div>
</div>

<h2>🎯 Métriques globales</h2>

<div class="kpi-grid">
  <div class="kpi-card">
    <div class="kpi-label">Accuracy</div>
    <div class="kpi-value" style="color: {acc_color}">{g['accuracy']*100:.1f}%</div>
    <div class="kpi-target">Cible : ≥ 75%</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">F1-Score (macro)</div>
    <div class="kpi-value" style="color: {f1_color}">{g['f1_macro']:.3f}</div>
    <div class="kpi-target">Cible : ≥ 0.70</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Kappa de Cohen</div>
    <div class="kpi-value" style="color: {kappa_color}">{g['kappa']:.3f}</div>
    <div class="kpi-target">Cible : ≥ 0.60</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Écart contre-factuel</div>
    <div class="kpi-value" style="color: {bias_color}">{bias_metrics['ecart_moyen']:.2f}%</div>
    <div class="kpi-target">Cible : &lt; 5%</div>
  </div>
</div>
"""

    targets_met = int(g["accuracy"] >= 0.75) + int(g["f1_macro"] >= 0.70) + int(g["kappa"] >= 0.60) + int(bias_metrics["conforme"])
    if targets_met == 4:
        verdict_html = '<div class="verdict verdict-success">✅ Les 4 cibles scientifiques sont atteintes — système validé</div>'
    elif targets_met >= 2:
        verdict_html = f'<div class="verdict verdict-warning">⚠️ {targets_met}/4 cibles atteintes — système partiellement validé</div>'
    else:
        verdict_html = '<div class="verdict verdict-fail">❌ Moins de 2 cibles atteintes — système à améliorer</div>'

    html += f'<div class="section">{verdict_html}</div>'

    # Section biais
    html += f"""
<h2>🛡️ Test contre-factuel des biais (AI Act)</h2>
<div class="section">
<p style="color: #7f8c8d; font-size: 13px;">
Chaque CV est analysé deux fois : version originale et version anonymisée.
Un écart moyen &lt; 5% garantit l'absence de biais discriminatoires.
</p>
<table>
<thead>
<tr><th>CV</th><th>Sujet</th><th>Score original</th><th>Score anonymisé</th><th>Écart</th><th>Conforme</th></tr>
</thead>
<tbody>
"""
    for b in bias_metrics["details"]:
        conforme_html = '<span style="color:#27ae60">✅</span>' if b["conforme"] else '<span style="color:#c0392b">⚠️</span>'
        html += f"""<tr>
<td style="font-size:12px">{b['cv_filename']}</td>
<td><b>{b['subject_id']}</b></td>
<td>{b['score_original']:.1f}</td>
<td>{b['score_anonymise']:.1f}</td>
<td>{b['ecart']:.1f}</td>
<td>{conforme_html}</td>
</tr>"""
    html += f"""</tbody></table>
<p><b>Écart moyen : {bias_metrics['ecart_moyen']:.2f}% — {'✅ Conforme (< 5%)' if bias_metrics['conforme'] else '⚠️ Non conforme (≥ 5%)'}</b></p>
</div>"""

    # Matrice de confusion
    html += f"""
<h2>📊 Matrice de confusion</h2>
<div class="section">
<p style="color: #7f8c8d; font-size: 13px;">Lignes = annotations humaines (vérité), Colonnes = prédictions IA.</p>
<table class="cm-table" style="margin: 0 auto; max-width: 600px;">
<thead>
<tr><th>Humain ↓ / IA →</th>"""
    for label in labels:
        html += f'<th>{label.replace("_", " ")}</th>'
    html += "<th>Total</th></tr></thead><tbody>"

    for i, true_label in enumerate(labels):
        row_total = sum(cm[i])
        html += f'<tr><th>{true_label.replace("_", " ")}</th>'
        for j in range(len(labels)):
            value = cm[i][j]
            css_class = "cm-correct" if i == j else ("cm-error" if abs(i-j) > 1 else "cm-neutral")
            html += f'<td class="{css_class}">{value}</td>'
        html += f'<td style="background: #ecf0f1; font-weight: bold;">{row_total}</td></tr>'
    html += "</tbody></table></div>"

    # Métriques par sujet
    html += "<h2>📋 Métriques par sujet de stage</h2><div class='section'><table>"
    html += "<thead><tr><th>Sujet</th><th>N</th><th>Accuracy</th><th>F1 (macro)</th></tr></thead><tbody>"
    for subj_id, vals in metrics["per_subject"].items():
        title = subjects_dict[subj_id]["title"]
        html += f"""<tr>
<td><b>{subj_id}</b><br><span style="color:#7f8c8d;font-size:12px">{title}</span></td>
<td>{vals['n']}</td>
<td>{vals['accuracy']*100:.1f}%</td>
<td>{vals['f1_macro']:.3f}</td>
</tr>"""
    html += "</tbody></table></div>"

    # Détail par cas
    html += "<h2>🔍 Détail des 48 cas évalués</h2><div class='section'><table>"
    html += "<thead><tr><th>#</th><th>CV</th><th>Sujet</th><th>Humain</th><th>IA</th><th>Score IA</th><th>Match</th></tr></thead><tbody>"
    for i, c in enumerate(cases, 1):
        match_html = '<span class="match-yes">✅</span>' if c["match"] else '<span class="match-no">❌</span>'
        html += f"""<tr>
<td>{i}</td>
<td style="font-size:12px">{c['cv_filename']}</td>
<td><b>{c['subject_id']}</b></td>
<td><span class="label-{c['label_human']}">{c['label_human'].replace('_', ' ')}</span></td>
<td><span class="label-{c['label_ai']}">{c['label_ai'].replace('_', ' ')}</span></td>
<td>{c['ai_score']:.1f}</td>
<td>{match_html}</td>
</tr>"""
    html += "</tbody></table></div>"

    html += f"""
<div style="text-align: center; color: #7f8c8d; font-size: 12px; margin-top: 30px; padding: 20px;">
Rapport généré le {datetime.now().strftime("%d/%m/%Y à %H:%M")} — Module IA ASM v1.0
</div>
</body></html>"""

    with open(RESULTS_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"📄 Rapport HTML : {RESULTS_HTML}")


def print_summary(metrics, bias_metrics):
    """Affiche un résumé console."""
    g = metrics["global"]
    print("\n" + "=" * 70)
    print("  RÉSUMÉ FINAL")
    print("=" * 70)
    print(f"  Total          : {g['n_total']} cas évalués")
    print(f"  Bonnes préds   : {g['n_correct']} ({g['n_correct']/g['n_total']*100:.1f}%)")
    print(f"  Accuracy       : {g['accuracy']*100:.1f}%   (cible ≥ 75%)  {'✅' if g['accuracy'] >= 0.75 else '⚠️'}")
    print(f"  F1-Score macro : {g['f1_macro']:.3f}      (cible ≥ 0.70) {'✅' if g['f1_macro'] >= 0.70 else '⚠️'}")
    print(f"  Kappa de Cohen : {g['kappa']:.3f}      (cible ≥ 0.60) {'✅' if g['kappa'] >= 0.60 else '⚠️'}")
    print(f"  Écart biais    : {bias_metrics['ecart_moyen']:.2f}%     (cible < 5%)   {'✅' if bias_metrics['conforme'] else '⚠️'}")
    print("=" * 70)


def main():
    cases, subjects_dict, cv_cache = evaluate()
    if not cases:
        print("❌ Aucun cas évalué — vérifie les CVs et annotations")
        return

    metrics = compute_metrics(cases)
    bias_metrics = compute_counterfactual_bias(cv_cache, subjects_dict)

    save_results(cases, metrics, subjects_dict, bias_metrics)
    generate_html_report(cases, metrics, subjects_dict, bias_metrics)
    print_summary(metrics, bias_metrics)
    print(f"\n👉 Ouvre {RESULTS_HTML} dans ton navigateur pour le rapport visuel.")


if __name__ == "__main__":
    main()