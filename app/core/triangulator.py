"""
================================================================================
TRIANGULATOR v2 — Vote PONDERE entre methodes d'extraction
================================================================================

CHANGEMENTS v2 :
- Vote PONDERE au lieu de vote simple (1 voix = 1 voix)
- Le LLM a un poids superieur (1.5) car il comprend le contexte
- Regex et NER ont un poids de 1.0 chacun
- En cas d'egalite ponderee, on prend la valeur la PLUS ELEVEE
  (philosophie : mieux vaut detecter trop que pas assez, le RH valide)

POURQUOI :
Avant : si regex=1, ner=1, llm=3 -> vote majoritaire dit 1 (2 contre 1)
Apres : poids regex(1) + ner(1) = 2 vs llm(1.5)*3 = 4.5 -> llm gagne
       Mais on prend la valeur moyenne ponderee : (1+1+3*1.5)/(1+1+1.5) = 1.86 ~ 2
================================================================================
"""

from typing import Any, Dict, List, Optional
from collections import Counter
from loguru import logger


# =============================================================================
# NIVEAUX DE CONFIANCE
# =============================================================================
CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"


# =============================================================================
# POIDS DES METHODES (nouveau v2)
# =============================================================================
METHOD_WEIGHTS = {
    "regex": 1.0,
    "ner":   1.0,
    "llm":   1.5,  # Plus de poids car le LLM comprend le contexte
}


def _get_weight(method_name: str) -> float:
    """Retourne le poids d'une methode (defaut 1.0)."""
    return METHOD_WEIGHTS.get(method_name, 1.0)


# =============================================================================
# VOTE POUR UNE VALEUR NUMERIQUE (ponderee)
# =============================================================================
def consensus_numeric(
    values: Dict[str, Optional[int]],
    tolerance: int = 0,
) -> Dict[str, Any]:
    """
    Vote majoritaire PONDERE pour une valeur numerique.

    Strategie :
    1. Filtrer les None
    2. Calculer la moyenne ponderee
    3. Si une valeur exacte recoit > 50% du poids total -> consensus fort (high)
    4. Sinon, prendre la moyenne ponderee arrondie + confiance medium/low

    Args:
        values : Dictionnaire {nom_methode: valeur_ou_None}
        tolerance : Ecart max pour considerer 2 valeurs comme "egales"
    """
    valid = {k: v for k, v in values.items() if v is not None}

    if not valid:
        return {
            "value": None,
            "confidence": CONFIDENCE_LOW,
            "sources": values,
            "agreement_count": 0,
            "reason": "Aucune methode n'a pu extraire la valeur",
        }

    # Cas trivial : une seule methode
    if len(valid) == 1:
        only_method, only_value = list(valid.items())[0]
        # Si c'est le LLM seul, on lui fait davantage confiance
        conf = CONFIDENCE_MEDIUM if only_method == "llm" else CONFIDENCE_LOW
        return {
            "value": only_value,
            "confidence": conf,
            "sources": values,
            "agreement_count": 1,
            "reason": f"Seule la methode '{only_method}' a fourni une valeur",
        }

    # =========================================================================
    # VOTE PONDERE
    # =========================================================================
    # 1. Calculer le poids total par valeur
    weighted_votes: Dict[int, float] = {}
    for method, value in valid.items():
        weight = _get_weight(method)
        weighted_votes[value] = weighted_votes.get(value, 0) + weight

    total_weight = sum(_get_weight(m) for m in valid.keys())

    # 2. Trouver la valeur avec le plus de poids
    best_value, best_weight = max(weighted_votes.items(), key=lambda x: x[1])
    weight_ratio = best_weight / total_weight

    # 3. Determiner la confiance
    if weight_ratio >= 0.9:
        # Quasi unanimite
        confidence = CONFIDENCE_HIGH
    elif weight_ratio >= 0.55:
        # Majorite claire
        confidence = CONFIDENCE_MEDIUM
    else:
        # Pas de majorite -> on prend la moyenne ponderee
        weighted_sum = sum(v * _get_weight(m) for m, v in valid.items())
        best_value = round(weighted_sum / total_weight)
        confidence = CONFIDENCE_LOW

    # 4. Heuristique speciale : si le LLM dit une valeur SUPERIEURE aux autres,
    #    et que cette valeur est plausible, on penche vers le LLM
    #    (le LLM est moins susceptible de "rater" un stage que regex/NER)
    if "llm" in valid:
        llm_value = valid["llm"]
        other_values = [v for m, v in valid.items() if m != "llm"]
        if other_values and llm_value > max(other_values):
            # Le LLM voit PLUS que les autres -> on lui donne le benefice du doute
            # On prend la moyenne entre LLM et le max des autres (au lieu du best_value)
            compromise = round((llm_value + max(other_values)) / 2)
            if compromise > best_value:
                logger.debug(
                    f"LLM a vote {llm_value} > autres {other_values}. "
                    f"Compromis a {compromise}"
                )
                best_value = compromise
                confidence = CONFIDENCE_MEDIUM

    return {
        "value": best_value,
        "confidence": confidence,
        "sources": values,
        "agreement_count": len([v for v in valid.values() if v == best_value]),
        "reason": f"Vote pondere : valeur={best_value} (poids {weight_ratio:.0%})",
    }


# =============================================================================
# VOTE POUR UNE VALEUR CATEGORIELLE (avec poids)
# =============================================================================
def consensus_categorical(values: Dict[str, Optional[str]]) -> Dict[str, Any]:
    """Vote pondere pour une valeur categorielle."""
    valid = {
        k: v.lower().strip()
        for k, v in values.items()
        if v and isinstance(v, str) and v.lower().strip() not in ("autre", "inconnu", "")
    }

    if not valid:
        return {
            "value": "autre",
            "confidence": CONFIDENCE_LOW,
            "sources": values,
            "agreement_count": 0,
            "reason": "Aucune categorie determinee",
        }

    if len(valid) == 1:
        only_method, only_value = list(valid.items())[0]
        conf = CONFIDENCE_MEDIUM if only_method == "llm" else CONFIDENCE_LOW
        return {
            "value": only_value,
            "confidence": conf,
            "sources": values,
            "agreement_count": 1,
            "reason": f"Seule '{only_method}' a fourni une categorie",
        }

    # Vote pondere
    weighted_votes: Dict[str, float] = {}
    for method, value in valid.items():
        weight = _get_weight(method)
        weighted_votes[value] = weighted_votes.get(value, 0) + weight

    total_weight = sum(_get_weight(m) for m in valid.keys())
    best_value, best_weight = max(weighted_votes.items(), key=lambda x: x[1])
    weight_ratio = best_weight / total_weight

    if weight_ratio >= 0.9:
        confidence = CONFIDENCE_HIGH
    elif weight_ratio >= 0.55:
        confidence = CONFIDENCE_MEDIUM
    else:
        confidence = CONFIDENCE_LOW

    return {
        "value": best_value,
        "confidence": confidence,
        "sources": values,
        "agreement_count": len([v for v in valid.values() if v == best_value]),
        "reason": f"Vote pondere categorique (poids {weight_ratio:.0%})",
    }


# =============================================================================
# VOTE POUR UNE VALEUR BOOLEENNE
# =============================================================================
def consensus_boolean(values: Dict[str, Optional[bool]]) -> Dict[str, Any]:
    """
    Vote pondere pour une valeur booleenne.
    Le LLM a poids 1.5, regex/NER ont poids 1.0.
    """
    valid = {k: v for k, v in values.items() if v is not None}

    if not valid:
        return {
            "value": False,
            "confidence": CONFIDENCE_LOW,
            "sources": values,
            "agreement_count": 0,
            "reason": "Aucune methode disponible",
        }

    true_weight = sum(_get_weight(m) for m, v in valid.items() if v)
    false_weight = sum(_get_weight(m) for m, v in valid.items() if not v)
    total = true_weight + false_weight

    if true_weight > false_weight:
        consensus_value = True
        weight_ratio = true_weight / total
    elif false_weight > true_weight:
        consensus_value = False
        weight_ratio = false_weight / total
    else:
        # Egalite -> on prefere False (plus conservateur)
        consensus_value = False
        weight_ratio = 0.5

    if weight_ratio >= 0.9:
        confidence = CONFIDENCE_HIGH
    elif weight_ratio >= 0.55:
        confidence = CONFIDENCE_MEDIUM
    else:
        confidence = CONFIDENCE_LOW

    return {
        "value": consensus_value,
        "confidence": confidence,
        "sources": values,
        "agreement_count": int(consensus_value) if consensus_value else int(not consensus_value),
        "reason": f"Vote pondere booleen (poids {weight_ratio:.0%})",
    }


# =============================================================================
# VOTE POUR UNE LISTE (union avec deduplication)
# =============================================================================
def consensus_list(
    values: Dict[str, Optional[List[str]]],
    min_methods: int = 1,
) -> Dict[str, Any]:
    """
    Union des elements, en gardant ceux mentionnes par au moins
    `min_methods` sources.
    """
    valid = {k: v for k, v in values.items() if v is not None}

    if not valid:
        return {
            "value": [],
            "confidence": CONFIDENCE_LOW,
            "sources": values,
            "agreement_count": 0,
            "reason": "Aucune liste disponible",
        }

    all_items: Dict[str, set] = {}
    for method, items in valid.items():
        for item in items:
            normalized = item.lower().strip()
            if normalized:
                all_items.setdefault(normalized, set()).add(method)

    consensus_items = [
        item for item, methods in all_items.items()
        if len(methods) >= min_methods
    ]

    total = len(valid)
    if not consensus_items:
        confidence = CONFIDENCE_LOW
    else:
        avg_agreement = sum(
            len(all_items[item]) for item in consensus_items
        ) / len(consensus_items)
        if avg_agreement >= total:
            confidence = CONFIDENCE_HIGH
        elif avg_agreement >= 2:
            confidence = CONFIDENCE_MEDIUM
        else:
            confidence = CONFIDENCE_LOW

    return {
        "value": consensus_items,
        "confidence": confidence,
        "sources": values,
        "agreement_count": len(consensus_items),
        "reason": f"{len(consensus_items)} items consensuels",
    }


# =============================================================================
# UTILITAIRE : score global de confiance
# =============================================================================
def overall_confidence(*consensus_results: Dict[str, Any]) -> str:
    """Calcule un score de confiance global."""
    if not consensus_results:
        return CONFIDENCE_LOW

    scores = []
    for r in consensus_results:
        c = r.get("confidence", CONFIDENCE_LOW)
        if c == CONFIDENCE_HIGH:
            scores.append(2)
        elif c == CONFIDENCE_MEDIUM:
            scores.append(1)
        else:
            scores.append(0)

    avg = sum(scores) / len(scores)

    if avg >= 1.7:
        return CONFIDENCE_HIGH
    elif avg >= 0.8:
        return CONFIDENCE_MEDIUM
    else:
        return CONFIDENCE_LOW