"""
Script d'extraction massive : analyse tous les CVs du dossier cvs/
et génère un rapport HTML + un JSON pour annotation.

Usage : python gold_dataset/extract_all_cvs.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

# Ajoute le dossier racine au path pour importer "app"
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.core.cv_parser import cv_parser  # noqa: E402


CVS_DIR = Path(__file__).parent / "cvs"
OUTPUT_JSON = Path(__file__).parent / "extractions.json"
OUTPUT_HTML = Path(__file__).parent / "extractions_report.html"


def extract_all():
    """Lance l'extraction sur tous les PDFs du dossier cvs/."""
    if not CVS_DIR.exists():
        print(f"❌ Dossier introuvable : {CVS_DIR}")
        return []

    pdf_files = sorted(CVS_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"❌ Aucun PDF trouvé dans {CVS_DIR}")
        return []

    print(f"📂 {len(pdf_files)} CVs trouvés dans {CVS_DIR}\n")
    results = []

    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"[{i}/{len(pdf_files)}] 🔍 Analyse : {pdf_path.name}...")
        try:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            data = cv_parser.parse(pdf_bytes)
            results.append({
                "filename": pdf_path.name,
                "size_kb": round(len(pdf_bytes) / 1024, 1),
                "extraction": data["extraction"],
                "skills": data["skills"],
                "ner": data["ner"],
                "raw_text_preview": data.get("raw_text_preview", ""),
                "status": "ok",
            })
            print(f"   ✅ {data['skills']['total']} compétences "
                  f"({data['extraction']['method']}, "
                  f"{data['extraction']['char_count']} chars)")
        except Exception as e:
            print(f"   ❌ Erreur : {e}")
            results.append({
                "filename": pdf_path.name,
                "status": "error",
                "error": str(e),
            })

    return results


def save_json(results: list):
    """Sauvegarde brute en JSON."""
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "total_cvs": len(results),
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n💾 JSON sauvegardé : {OUTPUT_JSON}")


def save_html(results: list):
    """Génère un rapport HTML lisible."""
    html = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Rapport d'extraction des CVs</title>
<style>
body { font-family: 'Segoe UI', sans-serif; max-width: 1100px; margin: 30px auto; padding: 20px; background: #f5f7fa; color: #2c3e50; }
h1 { color: #1e3a5f; border-bottom: 3px solid #1e3a5f; padding-bottom: 10px; }
h2 { color: #c0392b; margin-top: 25px; }
.cv-card { background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }
.cv-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #ecf0f1; }
.cv-title { font-size: 18px; font-weight: bold; color: #1e3a5f; }
.cv-meta { color: #7f8c8d; font-size: 13px; }
.method-native { background: #27ae60; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }
.method-ocr { background: #e67e22; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }
.section { margin-top: 12px; }
.section-title { font-weight: 600; color: #34495e; margin-bottom: 6px; font-size: 14px; }
.skill-tag { display: inline-block; background: #ebf5fb; color: #2874a6; padding: 3px 8px; margin: 2px; border-radius: 4px; font-size: 12px; }
.category { background: #f8f9fa; padding: 8px 12px; margin: 6px 0; border-radius: 4px; font-size: 13px; }
.cat-name { font-weight: 600; color: #16a085; }
.education-line { background: #fef9e7; padding: 6px 12px; margin: 4px 0; border-radius: 4px; font-size: 13px; border-left: 3px solid #f39c12; }
.error { color: #c0392b; background: #fadbd8; padding: 10px; border-radius: 4px; }
.summary { background: #1e3a5f; color: white; padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; }
.summary-stats { display: flex; gap: 30px; margin-top: 10px; }
.stat-block { font-size: 14px; }
.stat-num { font-size: 22px; font-weight: bold; }
table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
th { background: #34495e; color: white; padding: 8px; text-align: left; }
td { padding: 8px; border-bottom: 1px solid #ecf0f1; }
tr:hover { background: #f8f9fa; }
</style>
</head>
<body>
<h1>📊 Rapport d'extraction des CVs — Gold Dataset</h1>
"""

    # ------ Résumé ------
    ok = [r for r in results if r.get("status") == "ok"]
    err = [r for r in results if r.get("status") == "error"]
    native = sum(1 for r in ok if r["extraction"]["method"] == "native")
    ocr = sum(1 for r in ok if r["extraction"]["method"] == "ocr")
    avg_skills = sum(r["skills"]["total"] for r in ok) / len(ok) if ok else 0

    html += f"""
<div class="summary">
  <div style="font-size: 18px; font-weight: 600;">Résumé global</div>
  <div class="summary-stats">
    <div class="stat-block"><div class="stat-num">{len(results)}</div>CVs analysés</div>
    <div class="stat-block"><div class="stat-num">{native}</div>Natifs (PyMuPDF)</div>
    <div class="stat-block"><div class="stat-num">{ocr}</div>Scannés (OCR)</div>
    <div class="stat-block"><div class="stat-num">{len(err)}</div>Erreurs</div>
    <div class="stat-block"><div class="stat-num">{avg_skills:.1f}</div>Skills moyennes</div>
  </div>
</div>

<h2>📋 Tableau récapitulatif</h2>
<table>
<thead>
<tr><th>#</th><th>CV</th><th>Méthode</th><th>Pages</th><th>Skills</th><th>Formations</th><th>Années</th></tr>
</thead>
<tbody>
"""
    for i, r in enumerate(results, 1):
        if r.get("status") != "ok":
            html += f"<tr><td>{i}</td><td>{r['filename']}</td><td colspan='5' class='error'>Erreur : {r.get('error', '')}</td></tr>"
            continue
        method_class = f"method-{r['extraction']['method']}"
        html += f"""<tr>
<td>{i}</td>
<td><b>{r['filename']}</b></td>
<td><span class='{method_class}'>{r['extraction']['method']}</span></td>
<td>{r['extraction']['num_pages']}</td>
<td>{r['skills']['total']}</td>
<td>{len(r['ner']['education_lines'])}</td>
<td>{', '.join(str(y) for y in r['ner']['years']) or '—'}</td>
</tr>"""
    html += "</tbody></table>"

    # ------ Détail par CV ------
    html += "<h2>🔍 Détail par CV</h2>"

    for i, r in enumerate(results, 1):
        if r.get("status") != "ok":
            html += f"""<div class="cv-card">
<div class="cv-title">{i}. {r['filename']}</div>
<div class="error">⚠️ Erreur d'extraction : {r.get('error', '')}</div>
</div>"""
            continue

        method_class = f"method-{r['extraction']['method']}"
        html += f"""
<div class="cv-card">
  <div class="cv-header">
    <div>
      <div class="cv-title">{i}. {r['filename']}</div>
      <div class="cv-meta">{r['size_kb']} KB · {r['extraction']['num_pages']} page(s) · {r['extraction']['char_count']} caractères</div>
    </div>
    <span class='{method_class}'>{r['extraction']['method'].upper()}</span>
  </div>

  <div class="section">
    <div class="section-title">🎯 Compétences détectées ({r['skills']['total']})</div>
"""
        # Skills par catégorie
        for cat, skills in r["skills"].get("by_category", {}).items():
            cat_short = cat.replace("informatique.", "").replace("transversal.", "").replace("_", " ")
            html += f'<div class="category"><span class="cat-name">{cat_short}:</span> '
            html += " ".join(f'<span class="skill-tag">{s}</span>' for s in skills)
            html += "</div>"

        # Formation
        html += '<div class="section"><div class="section-title">🎓 Lignes de formation</div>'
        if r["ner"]["education_lines"]:
            for line in r["ner"]["education_lines"]:
                html += f'<div class="education-line">{line}</div>'
        else:
            html += "<em>Aucune ligne de formation détectée</em>"
        html += "</div>"

        # Années
        if r["ner"]["years"]:
            html += f'<div class="section"><div class="section-title">📅 Années détectées</div>{", ".join(str(y) for y in r["ner"]["years"])}</div>'

        html += "</div>"  # fin cv-card

    html += "</body></html>"

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"📄 Rapport HTML : {OUTPUT_HTML}")


def main():
    print("=" * 60)
    print("  EXTRACTION MASSIVE — Gold Dataset")
    print("=" * 60)
    results = extract_all()
    if not results:
        return
    save_json(results)
    save_html(results)
    print("\n✅ Terminé ! Ouvre le rapport HTML dans ton navigateur.")
    print(f"   → {OUTPUT_HTML}")


if __name__ == "__main__":
    main()