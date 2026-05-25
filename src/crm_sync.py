import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

_SCHEMA = "pipeline"


def _engine():
    url = os.environ["LEAD_PIPELINE_DATABASE_URL"]
    return create_engine(url, poolclass=NullPool)


def log_event(lead_id: str, event_type: str, payload: Optional[dict] = None) -> None:
    """Append an event row to pipeline.events.

    Args:
        lead_id: UUID of the lead.
        event_type: One of: ingested, deduped, scored, routed, contacted, converted.
        payload: Optional dict with event-specific context.
    """
    with _engine().begin() as conn:
        conn.execute(
            text(f"""
                insert into {_SCHEMA}.events (lead_id, event_type, payload, created_at)
                values (:lead_id::uuid, :event_type, :payload::jsonb, :now)
            """),
            {
                "lead_id": lead_id,
                "event_type": event_type,
                "payload": json.dumps(payload or {}),
                "now": datetime.now(timezone.utc),
            },
        )
    logger.debug("Logged event %s for lead %s", event_type, lead_id)


def record_contact(lead_id: str, contacted_at: Optional[datetime] = None) -> None:
    """Mark a lead as contacted and compute speed_to_contact_min.

    Args:
        lead_id: UUID of the lead.
        contacted_at: When contact was made (defaults to now).
    """
    contacted_at = contacted_at or datetime.now(timezone.utc)
    with _engine().begin() as conn:
        conn.execute(
            text(f"""
                update {_SCHEMA}.leads
                set speed_to_contact_min = extract(epoch from (:contacted_at - created_at)) / 60,
                    updated_at = :contacted_at
                where id = :lead_id::uuid
            """),
            {"lead_id": lead_id, "contacted_at": contacted_at},
        )
    log_event(lead_id, "contacted", {"contacted_at": contacted_at.isoformat()})
    logger.info("Recorded contact for lead %s", lead_id)
