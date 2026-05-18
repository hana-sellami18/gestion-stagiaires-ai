"""
Wrapper SBERT — chargement unique du modèle + calcul de similarité.
Le modèle prend ~5s à charger au démarrage, mais ensuite chaque calcul est rapide.
"""
from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer
from loguru import logger

from app.config import settings


class SBERTClient:
    """Client unique pour les embeddings et la similarité."""

    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.sbert_model
        logger.info(f"Chargement SBERT : {self.model_name} (peut prendre ~5s)")
        self.model = SentenceTransformer(self.model_name)
        logger.info("SBERT prêt.")

    def encode(self, texts: list[str] | str) -> np.ndarray:
        """Convertit du texte en vecteurs (embeddings)."""
        if isinstance(texts, str):
            texts = [texts]
        return self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

    def similarity(self, text_a: str, text_b: str) -> float:
        """Similarité cosinus entre deux textes (0 à 1)."""
        emb = self.encode([text_a, text_b])
        # Cosinus = produit scalaire / (norme_a * norme_b)
        cos = np.dot(emb[0], emb[1]) / (np.linalg.norm(emb[0]) * np.linalg.norm(emb[1]))
        # Clamp entre 0 et 1 (parfois -très petit- à cause de flottants)
        return float(max(0.0, min(1.0, cos)))

    def best_match(self, query: str, candidates: list[str]) -> tuple[str, float]:
        """Trouve le meilleur match parmi des candidats."""
        if not candidates:
            return ("", 0.0)
        all_texts = [query] + candidates
        emb = self.encode(all_texts)
        query_emb = emb[0]
        cand_emb = emb[1:]
        sims = np.dot(cand_emb, query_emb) / (
            np.linalg.norm(cand_emb, axis=1) * np.linalg.norm(query_emb) + 1e-8
        )
        best_idx = int(np.argmax(sims))
        return (candidates[best_idx], float(sims[best_idx]))


# Singleton global
@lru_cache(maxsize=1)
def get_sbert() -> SBERTClient:
    """Lazy-loading du SBERT (chargé au premier appel seulement)."""
    return SBERTClient()