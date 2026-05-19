import json

with open("gold_dataset/evaluation_results.json", "r", encoding="utf-8") as f:
    d = json.load(f)

print("Clés racine:", list(d.keys()))
print()

# Cherche la liste des cas
for key in d.keys():
    val = d[key]
    if isinstance(val, list) and len(val) > 0:
        print(f"Clé '{key}' = liste de {len(val)} éléments")
        print(f"Premier élément:")
        print(json.dumps(val[0], indent=2, ensure_ascii=False))
        print()