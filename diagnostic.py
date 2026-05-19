import json
from collections import Counter

with open("gold_dataset/evaluation_results.json", "r", encoding="utf-8") as f:
    d = json.load(f)

cases = d["cases"]
print(f"Total cas: {len(cases)}\n")

# 1. Distribution des erreurs (sens du désaccord)
print("="*70)
print("SENS DES ERREURS (humain -> IA)")
print("="*70)
errors_direction = Counter()
for c in cases:
    if not c["match"]:
        errors_direction[(c["label_human"], c["label_ai"])] += 1

for (h, ai), n in sorted(errors_direction.items(), key=lambda x: -x[1]):
    print(f"  humain={h:<25} -> IA={ai:<25} : {n}")

# 2. Cas sous-notés (humain pense mieux que IA)
print("\n" + "="*70)
print("CAS SOUS-NOTES (IA trop sévère)")
print("="*70)
order = {"PEU_ADAPTE": 0, "PARTIELLEMENT_ADAPTE": 1, "ADAPTE": 2}
sous_notes = [c for c in cases if order[c["label_ai"]] < order[c["label_human"]]]
sur_notes = [c for c in cases if order[c["label_ai"]] > order[c["label_human"]]]

print(f"Sous-notes: {len(sous_notes)} cas")
print(f"Sur-notes : {len(sur_notes)} cas")

# 3. Détail des sous-notes par sujet
print("\n" + "="*70)
print("SOUS-NOTATION PAR SUJET")
print("="*70)
by_subject = Counter(c["subject_id"] for c in sous_notes)
for subj, n in sorted(by_subject.items(), key=lambda x: -x[1]):
    print(f"  {subj}: {n} cas sous-notés")

# 4. Pilier qui pose problème dans les sous-notes
print("\n" + "="*70)
print("MOYENNE DES PILIERS DANS LES CAS SOUS-NOTES")
print("="*70)
if sous_notes:
    pillars_all = {}
    for c in sous_notes:
        for k, v in c["pillars"].items():
            pillars_all.setdefault(k, []).append(v)
    for k, vals in pillars_all.items():
        print(f"  {k:<15}: moyenne = {sum(vals)/len(vals):.1f}")

# 5. Liste détaillée des 15 premiers cas sous-notés
print("\n" + "="*70)
print("DETAIL DES 15 PREMIERS CAS SOUS-NOTES")
print("="*70)
for c in sous_notes[:15]:
    print(f"{c['cv_filename'][:35]:<35} | {c['subject_id']:<12} | "
          f"humain={c['label_human']:<22} ai={c['label_ai']:<22} "
          f"score={c['ai_score']} | pillars={c['pillars']}")