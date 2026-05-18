"""Endpoints de consultation du journal d'audit (admin uniquement en prod)."""
from fastapi import APIRouter, Query

from app.core.audit_logger import audit_logger

router = APIRouter(prefix="/api/admin/audit", tags=["Audit"])


@router.get("")
async def get_audit_log(
    limit: int = Query(50, ge=1, le=500, description="Nombre maximum d'entrées"),
    event: str = Query(None, description="Filtre : CV_ANALYSIS | SCORING | INTERVIEW_GENERATION"),
):
    """
    Retourne les N dernières entrées du journal d'audit (les plus récentes en premier).
    Conformité AI Act art. 12 + RGPD art. 22.
    """
    events = audit_logger.read_audit_log(limit=limit, event_filter=event)
    return {
        "total_returned": len(events),
        "filter_event": event,
        "events": events,
    }


@router.get("/stats")
async def get_audit_stats():
    """Statistiques basiques du journal d'audit."""
    all_events = audit_logger.read_audit_log(limit=10000)

    stats = {
        "total_events": len(all_events),
        "by_event_type": {},
        "by_recommendation": {},
        "average_duration_ms": {},
    }

    durations_by_type: dict[str, list[float]] = {}

    for event in all_events:
        evt_type = event.get("event", "UNKNOWN")
        stats["by_event_type"][evt_type] = stats["by_event_type"].get(evt_type, 0) + 1

        if evt_type == "SCORING":
            reco = event.get("recommendation", "UNKNOWN")
            stats["by_recommendation"][reco] = stats["by_recommendation"].get(reco, 0) + 1

        if "duration_ms" in event:
            durations_by_type.setdefault(evt_type, []).append(event["duration_ms"])

    for evt_type, durations in durations_by_type.items():
        stats["average_duration_ms"][evt_type] = round(sum(durations) / len(durations), 1)

    return stats