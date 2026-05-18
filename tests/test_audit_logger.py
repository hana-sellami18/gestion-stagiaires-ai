"""Tests pour audit_logger.py."""
from app.core.audit_logger import audit_logger


class TestAuditLogger:

    def test_log_cv_analysis(self, sample_cv_data):
        """L'audit d'une analyse CV retourne bien un audit_id."""
        audit_id = audit_logger.log_cv_analysis(
            filename="test_cv.pdf",
            cv_data=sample_cv_data,
            duration_ms=123.4,
        )
        assert audit_id
        assert len(audit_id) == 8  # UUID4 tronqué à 8 chars

    def test_read_audit_log(self, sample_cv_data):
        """Lecture des logs après écriture."""
        # On écrit un événement
        audit_logger.log_cv_analysis(
            filename="test_read.pdf",
            cv_data=sample_cv_data,
            duration_ms=50.0,
        )

        # On le relit
        events = audit_logger.read_audit_log(limit=5)
        assert len(events) >= 1
        # Le plus récent doit être en premier
        latest = events[0]
        assert "audit_id" in latest
        assert "timestamp" in latest
        assert "event" in latest

    def test_filter_by_event_type(self, sample_cv_data):
        """Filtrage par type d'événement."""
        # On écrit
        audit_logger.log_cv_analysis(
            filename="test_filter.pdf",
            cv_data=sample_cv_data,
            duration_ms=10.0,
        )
        # On filtre
        events = audit_logger.read_audit_log(limit=10, event_filter="CV_ANALYSIS")
        for e in events:
            assert e["event"] == "CV_ANALYSIS"

    def test_filename_hash_anonymizes(self):
        """Les noms de fichiers sont hachés (RGPD)."""
        h1 = audit_logger._hash("Chaima_HAMDAOUI_CV.pdf")
        h2 = audit_logger._hash("Chaima_HAMDAOUI_CV.pdf")
        h3 = audit_logger._hash("Other_CV.pdf")
        assert h1 == h2  # Même input → même hash
        assert h1 != h3  # Inputs différents → hashs différents
        assert len(h1) == 12