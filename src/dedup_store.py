import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from src.ingestor import Lead

logger = logging.getLogger(__name__)

_SCHEMA = "pipeline"
_TABLE = "leads"


def _engine():
    url = os.environ["LEAD_PIPELINE_DATABASE_URL"]
    return create_engine(url, poolclass=NullPool)


def init_store() -> None:
    """Run the schema migration idempotently."""
    import pathlib
    migration = pathlib.Path(__file__).resolve().parents[1] / "migrations" / "001_create_leads_schema.sql"
    sql = migration.read_text()
    with _engine().begin() as conn:
        conn.execute(text(sql))
    logger.info("Dedup store initialized (%s.%s)", _SCHEMA, _TABLE)


def is_duplicate(lead: Lead) -> bool:
    """Return True if a lead with this email or phone already exists."""
    with _engine().connect() as conn:
        result = conn.execute(
            text(f"""
                select 1 from {_SCHEMA}.{_TABLE}
                where email = :email
                   or (phone is not null and phone = :phone and :phone is not null)
                limit 1
            """),
            {"email": lead.email, "phone": lead.phone},
        )
        return result.fetchone() is not None


def fetch_by_email(email: str) -> Optional[dict]:
    """Return score, tier, assigned_to for an existing lead, or None if not found."""
    with _engine().connect() as conn:
        row = conn.execute(
            text(f"select id, score, tier, assigned_to from {_SCHEMA}.{_TABLE} where email = :email"),
            {"email": email},
        ).fetchone()
    if row is None:
        return None
    return {"id": str(row.id), "score": row.score, "tier": row.tier, "assigned_to": row.assigned_to}


def upsert(lead: Lead, score: Optional[int] = None, tier: Optional[str] = None, assigned_to: Optional[str] = None) -> str:
    """Insert lead or update score/tier if it already exists. Returns the lead's UUID."""
    with _engine().begin() as conn:
        result = conn.execute(
            text(f"""
                insert into {_SCHEMA}.{_TABLE}
                    (email, phone, name, company, source, industry_context, raw_payload, score, tier, assigned_to, updated_at)
                values
                    (:email, :phone, :name, :company, :source, :industry_context, :raw_payload::jsonb, :score, :tier, :assigned_to, :now)
                on conflict (email) do update set
                    phone            = excluded.phone,
                    name             = excluded.name,
                    company          = excluded.company,
                    industry_context = excluded.industry_context,
                    raw_payload      = excluded.raw_payload,
                    score            = excluded.score,
                    tier             = excluded.tier,
                    assigned_to      = excluded.assigned_to,
                    updated_at       = excluded.updated_at
                returning id
            """),
            {
                "email": lead.email,
                "phone": lead.phone,
                "name": lead.name,
                "company": lead.company,
                "source": lead.source,
                "industry_context": lead.industry_context,
                "raw_payload": json.dumps(lead.raw_payload),
                "score": score,
                "tier": tier,
                "assigned_to": assigned_to,
                "now": datetime.now(timezone.utc),
            },
        )
        row = result.fetchone()
        return str(row[0])
