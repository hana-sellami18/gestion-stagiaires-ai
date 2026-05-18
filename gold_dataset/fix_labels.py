import json

INPUT_FILE = "clean_dataset.json"
OUTPUT_FILE = "clean_dataset_fixed.json"


def compute_label(score):
    if score >= 85:
        label = "ADAPTE"
    elif score >= 70:
        label = "PARTIELLEMENT_ADAPTE"
    else:
        label = "PEU_ADAPTE"

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

count = 0

for case in data["cases"]:
    new_label = compute_label(case["ai_score"])

    if case["label_human"] != new_label:
        case["label_human"] = new_label
        count += 1

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"✅ Terminé : {count} labels corrigés")