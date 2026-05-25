import json
import logging
import os
from typing import Optional

import anthropic

from src.ingestor import Lead

logger = logging.getLogger(__name__)

_client: Optional[anthropic.Anthropic] = None

_SYSTEM_PROMPT = """You are a lead scoring assistant for a high-volume sales operation.

Score each inbound lead from 1 to 100 based on purchase intent and fit signals.

Scoring criteria:
- Intent signals (max 40 points):
  Explicit urgency language ("urgent", "asap", "immediately") = 10
  Specific budget or funding amount mentioned = 10
  Decision-maker title (owner, CEO, director, VP) = 10
  Clear problem statement or pain point = 10

- Business quality (max 30 points):
  Established company name present = 10
  Professional email domain (not gmail/yahoo/hotmail) = 10
  Phone number provided = 10

- Source quality (max 20 points):
  Paid ad sources (facebook_ad, google_ad, linkedin_ad) = 20
  Referral or partner = 15
  Organic / direct = 10
  Unknown = 5

- Completeness (max 10 points):
  All fields populated = 10
  Most fields populated = 5
  Minimal fields = 0

Return ONLY a JSON object with these fields:
- "score": integer 1-100
- "reasoning": one sentence explaining the score
- "signals": list of up to 3 short signal strings that most influenced the score (e.g. ["urgency language", "decision-maker title", "paid ad source"])
"""


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def score_lead(lead: Lead, industry_context: Optional[str] = None) -> tuple[int, str, list[str]]:
    """Score a lead using Claude.

    Args:
        lead: Normalized Lead object.
        industry_context: Optional client-specific context to include in the prompt.

    Returns:
        Tuple of (score, reasoning, signals).
    """
    context = industry_context or lead.industry_context or os.environ.get("INDUSTRY_CONTEXT", "B2B sales")

    user_message = json.dumps({
        "industry_context": context,
        "email": lead.email,
        "name": lead.name,
        "company": lead.company,
        "phone": lead.phone,
        "source": lead.source,
        "raw_payload": lead.raw_payload,
    })

    # Haiku sufficient here: structured JSON extraction from a fixed schema, no creative reasoning needed
    response = _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
        score = max(1, min(100, int(parsed["score"])))
        reasoning = str(parsed["reasoning"])
        signals = [str(s) for s in parsed.get("signals", [])][:3]
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error("Failed to parse Claude response for %s: %s | raw: %s", lead.email, e, raw)
        score = 1
        reasoning = "Scoring failed — review manually"
        signals = []

    logger.info("Scored %s (%s): %d/100 — %s", lead.email, lead.source, score, reasoning[:80])
    return score, reasoning, signals
