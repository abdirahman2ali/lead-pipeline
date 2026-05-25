import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".claude" / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

from fastapi import FastAPI, HTTPException  # noqa: E402
from pydantic import BaseModel, EmailStr  # noqa: E402

from src import crm_sync, dedup_store, ingestor, notifier, router, scorer  # noqa: E402

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    dedup_store.init_store()
    yield


app = FastAPI(title="Lead Pipeline API", lifespan=lifespan)


class LeadRequest(BaseModel):
    email: EmailStr
    name: str
    source: str
    phone: str = ""
    company: str = ""
    industry_context: str = ""


class LeadResponse(BaseModel):
    lead_id: str
    email: str
    score: int
    tier: str
    assigned_to: str
    duplicate: bool


@app.post("/leads", response_model=LeadResponse)
def ingest_lead(body: LeadRequest) -> LeadResponse:
    """Ingest a lead via webhook. Returns score, tier, and assigned rep."""
    try:
        lead = ingestor.normalize(body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    is_dup = dedup_store.is_duplicate(lead)
    lead_id = dedup_store.upsert(lead)
    crm_sync.log_event(lead_id, "ingested", {"source": lead.source, "duplicate": is_dup})

    if is_dup:
        crm_sync.log_event(lead_id, "deduped")
        logger.info("Duplicate lead received: %s", lead.email)
        existing = dedup_store.fetch_by_email(lead.email) or {}
        return LeadResponse(
            lead_id=lead_id,
            email=lead.email,
            score=existing.get("score") or 0,
            tier=existing.get("tier") or "unknown",
            assigned_to=existing.get("assigned_to") or "unassigned",
            duplicate=True,
        )

    score, reasoning, signals = scorer.score_lead(lead)
    tier, rep = router.route(score)

    dedup_store.upsert(lead, score=score, tier=tier, assigned_to=rep)
    crm_sync.log_event(lead_id, "scored", {"score": score, "reasoning": reasoning, "signals": signals})
    crm_sync.log_event(lead_id, "routed", {"tier": tier, "assigned_to": rep})

    if tier == "hot":
        notifier.send_hot_lead_alert(lead, score, tier, rep, reasoning, signals)

    return LeadResponse(
        lead_id=lead_id,
        email=lead.email,
        score=score,
        tier=tier,
        assigned_to=rep,
        duplicate=False,
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
