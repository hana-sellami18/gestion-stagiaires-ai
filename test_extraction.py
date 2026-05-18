"""Test simple pour voir ce que le pdf_extractor extrait du CV d'Emna."""

from app.core.pdf_extractor import pdf_extractor

# Le bon chemin (avec ESPACE entre CV et Emna)
pdf_path = r"C:\Users\ousse\Downloads\AI-main\AI-main\gold_dataset\cvs\CV Emna_br.pdf"

result = pdf_extractor.extract(pdf_path)

print("=" * 70)
print("TEXTE EXTRAIT (1500 premiers caracteres)")
print("=" * 70)
print(result["text"][:1500])
print()
print("=" * 70)
print(f"Total caracteres : {result['char_count']}")
print(f"Methode : {result['method']}")
print(f"Pages : {result['num_pages']}")
print("=" * 70)

# Recherches importantes
text = result["text"]
text_lower = text.lower()

print()
print("RECHERCHES :")
print(f"  'licence' trouve         : {'licence' in text_lower}")
print(f"  '3e' ou '3eme' trouve    : {'3e ' in text_lower or '3eme' in text_lower or '3ème' in text_lower}")
print(f"  'annee' / 'annee'        : {'année' in text_lower or 'annee' in text_lower}")
print(f"  'informatique' trouve    : {'informatique' in text_lower}")

# Verification caracteres turcs (le probleme suspect)
print()
print("CARACTERES SPECIAUX :")
print(f"  'I' turc (Idot)          : {'İ' in text}")
print(f"  'i' turc sans point      : {'ı' in text}")

# Afficher la partie qui contient le titre
print()
print("LIGNES CONTENANT 'LICENCE' OU 'ANNEE' :")
print("-" * 70)
for line in text.split("\n"):
    line_l = line.lower()
    if "licence" in line_l or "année" in line_l or "annee" in line_l or "lİcence" in line_l.lower():
        print(f"  >> {line.strip()}")