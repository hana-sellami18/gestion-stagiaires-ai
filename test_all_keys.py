from app.config import settings
from groq import Groq

keys = [
    settings.groq_api_key,
    settings.groq_api_key_2,
    settings.groq_api_key_3,
    settings.groq_api_key_4,
    settings.groq_api_key_5,
    settings.groq_api_key_6,
    settings.groq_api_key_7,
    settings.groq_api_key_8,
]

for i, key in enumerate(keys, 1):
    if not key:
        print(f"Cle #{i} : VIDE")
        continue
    try:
        client = Groq(api_key=key)
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": "ok"}],
            max_tokens=5
        )
        print(f"Cle #{i} ({key[:12]}...) : OK")
    except Exception as e:
        err = str(e)[:80]
        if "429" in err or "rate_limit" in err:
            print(f"Cle #{i} ({key[:12]}...) : RATE LIMIT")
        elif "401" in err or "invalid" in err.lower():
            print(f"Cle #{i} ({key[:12]}...) : INVALIDE")
        else:
            print(f"Cle #{i} ({key[:12]}...) : ERREUR - {err}")