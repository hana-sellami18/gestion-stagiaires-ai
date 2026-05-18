"""
Wrapper LLM — supporte Ollama (local) et Groq (cloud).

Choix du provider via la variable LLM_PROVIDER dans .env :
- "ollama" : LLM local (LLaMA 3.1 via Ollama)
- "groq"   : LLM cloud (LLaMA 3.3 70B via Groq, beaucoup plus rapide)

Fonctionnalités ajoutées :
- Rotation automatique entre plusieurs clés Groq sur RateLimitError (429)
- Cache LLM par CV : un seul appel par CV même si scoré sur 7 sujets × 2
  => divise la consommation de tokens par 14
"""

import json
import hashlib
from typing import Optional
from loguru import logger
from app.config import settings


# =============================================================================
# CACHE LLM GLOBAL
# Clé = hash du texte CV → valeur = résultat JSON extrait
# Evite de rappeler le LLM pour le même CV (original vs anonymisé,
# ou le même CV évalué sur plusieurs sujets).
# =============================================================================
_llm_cache: dict = {}


def get_cache_key(text: str) -> str:
    """Hash SHA256 des 2000 premiers caractères du CV (suffisant pour l'identifier)."""
    return hashlib.sha256(text[:2000].encode("utf-8")).hexdigest()


def get_cached(text: str) -> Optional[dict]:
    key = get_cache_key(text)
    if key in _llm_cache:
        logger.debug(f"Cache LLM HIT — clé {key[:12]}...")
        return _llm_cache[key]
    return None


def set_cached(text: str, result: dict) -> None:
    key = get_cache_key(text)
    _llm_cache[key] = result
    logger.debug(f"Cache LLM SET — clé {key[:12]}... ({len(_llm_cache)} entrées)")


def clear_cache() -> None:
    """Vide le cache (utile entre deux runs d'évaluation)."""
    _llm_cache.clear()
    logger.info("Cache LLM vidé")


# =============================================================================
# CLIENT OLLAMA (existant, inchangé)
# =============================================================================
class OllamaClient:
    """Client pour communiquer avec Ollama (local)."""

    def __init__(self):
        import httpx
        self.host = settings.ollama_host
        self.model = settings.ollama_model
        self.timeout = 120.0
        self.httpx = httpx

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        format: Optional[str] = None,
    ) -> str:
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system
        if format:
            payload["format"] = format

        logger.info(f"Appel Ollama ({self.model}) - prompt: {len(prompt)} chars")

        try:
            with self.httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "").strip()
        except self.httpx.TimeoutException:
            logger.error("Timeout Ollama")
            raise RuntimeError("Ollama timeout - modele trop lent ou indisponible")
        except Exception as e:
            logger.exception("Erreur Ollama")
            raise RuntimeError(f"Erreur Ollama : {e}")

    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.5,
    ) -> dict:
        raw = self.generate(prompt, system=system, temperature=temperature, format="json")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Reponse Ollama non-JSON : {raw[:200]}...")
            raise RuntimeError(f"Ollama n'a pas retourne un JSON valide : {e}")


# =============================================================================
# CLIENT GROQ avec rotation automatique des clés API
# =============================================================================
class GroqClient:
    """
    Client pour Groq Cloud API avec rotation automatique des clés.

    Configuration dans .env :
      GROQ_API_KEY=gsk_cle1...          # clé principale (obligatoire)
      GROQ_API_KEY_2=gsk_cle2...        # clés de secours (optionnelles)
      GROQ_API_KEY_3=gsk_cle3...
      GROQ_API_KEY_4=gsk_cle4...

    Sur RateLimitError (429), bascule automatiquement vers la clé suivante.
    Si toutes les clés sont épuisées, lève une RuntimeError.
    """

    def __init__(self):
        try:
            from groq import Groq
        except ImportError:
            raise RuntimeError(
                "Le SDK Groq n'est pas installe. Lance : pip install groq"
            )

        if not settings.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY manquante dans .env. "
                "Obtenir une cle gratuite sur https://console.groq.com/"
            )

        self._Groq = Groq
        self.model = settings.groq_model

        # Collecter toutes les clés disponibles
        self._api_keys = self._collect_api_keys()
        self._key_index = 0

        logger.info(
            f"GroqClient initialisé avec {len(self._api_keys)} clé(s) API — "
            f"rotation automatique activée"
        )

        # Créer le client avec la première clé
        self.client = self._Groq(api_key=self._api_keys[0])

    def _collect_api_keys(self) -> list:
        """
        Récupère toutes les clés Groq disponibles depuis settings.
        Cherche : GROQ_API_KEY, GROQ_API_KEY_2, GROQ_API_KEY_3, GROQ_API_KEY_4
        """
        keys = []

        # Clé principale
        if settings.groq_api_key:
            keys.append(settings.groq_api_key)

        # Clés supplémentaires (attributs optionnels dans settings)
        for i in range(2, 10):
            attr = f"groq_api_key_{i}"
            key = getattr(settings, attr, None)
            if key and key.strip():
                keys.append(key.strip())

        return keys

    def _rotate_key(self) -> bool:
        """
        Passe à la clé suivante.
        Retourne True si une nouvelle clé est disponible, False si toutes épuisées.
        """
        next_index = self._key_index + 1
        if next_index >= len(self._api_keys):
            logger.error(
                f"Toutes les clés Groq sont épuisées ({len(self._api_keys)} clé(s) testée(s)). "
                f"Attends le reset du quota (minuit UTC) ou ajoute GROQ_API_KEY_2 dans .env"
            )
            return False

        self._key_index = next_index
        new_key = self._api_keys[self._key_index]
        self.client = self._Groq(api_key=new_key)
        logger.warning(
            f"RateLimit atteint — rotation vers clé #{self._key_index + 1} "
            f"({new_key[:8]}...)"
        )
        return True

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        format: Optional[str] = None,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        # Tentative avec rotation automatique des clés
        while True:
            logger.info(
                f"Appel Groq ({self.model}) clé #{self._key_index + 1} "
                f"— prompt: {len(prompt)} chars"
            )
            try:
                response = self.client.chat.completions.create(**kwargs)
                return response.choices[0].message.content.strip()

            except Exception as e:
                error_str = str(e)

                # Rate limit → rotation de clé
                if "429" in error_str or "rate_limit_exceeded" in error_str:
                    logger.warning(f"Rate limit clé #{self._key_index + 1} : {error_str[:120]}")
                    if self._rotate_key():
                        # Retry automatiquement avec la nouvelle clé
                        continue
                    else:
                        # Toutes les clés épuisées
                        raise RuntimeError(
                            "Toutes les clés Groq sont épuisées (RateLimit 429). "
                            "Ajoute GROQ_API_KEY_2, GROQ_API_KEY_3 dans ton .env "
                            "ou attends le reset du quota (minuit UTC)."
                        )

                # Autre erreur → on log et on remonte
                logger.exception("Erreur Groq")
                raise RuntimeError(f"Erreur Groq : {e}")

    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.5,
    ) -> dict:
        raw = self.generate(prompt, system=system, temperature=temperature, format="json")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"Reponse Groq non-JSON : {raw[:200]}...")
            raise RuntimeError(f"Groq n'a pas retourne un JSON valide : {e}")


# =============================================================================
# FACTORY : choix automatique du provider selon .env
# =============================================================================
def _create_client():
    """Cree le bon client selon LLM_PROVIDER dans .env."""
    provider = settings.llm_provider.lower()

    if provider == "groq":
        logger.info("LLM provider : GROQ (cloud, rapide)")
        return GroqClient()
    elif provider == "ollama":
        logger.info("LLM provider : OLLAMA (local)")
        return OllamaClient()
    else:
        raise ValueError(
            f"LLM_PROVIDER='{provider}' invalide. Utilisez 'groq' ou 'ollama'."
        )


# =============================================================================
# SINGLETON
# =============================================================================
llm_client = _create_client()