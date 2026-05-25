import logging
import os
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_config_cache: Optional[dict] = None
_rep_index: int = 0


def _load_config() -> dict:
    global _config_cache
    if _config_cache is None:
        config_path = Path(__file__).resolve().parents[1] / "config" / "routing.yaml"
        with open(config_path) as f:
            _config_cache = yaml.safe_load(f)
    return _config_cache


def _rep_pool() -> list[str]:
    env_pool = os.environ.get("REP_POOL", "")
    if env_pool:
        return [r.strip() for r in env_pool.split(",") if r.strip()]
    return _load_config().get("default_rep_pool", ["unassigned@company.com"])


def assign_tier(score: int) -> str:
    """Return tier string based on score and routing config."""
    tiers = _load_config().get("tiers", {})
    if score >= tiers.get("hot", {}).get("min_score", 75):
        return "hot"
    if score >= tiers.get("warm", {}).get("min_score", 50):
        return "warm"
    return "cold"


def assign_rep(tier: str) -> str:
    """Assign a rep from the pool via round-robin."""
    global _rep_index
    pool = _rep_pool()
    if not pool:
        return "unassigned"
    rep = pool[_rep_index % len(pool)]
    _rep_index += 1
    logger.debug("Assigned %s rep: %s (tier: %s)", tier, rep, tier)
    return rep


def route(score: int) -> tuple[str, str]:
    """Return (tier, assigned_rep) for a given score.

    Args:
        score: Integer score 1-100.

    Returns:
        Tuple of (tier, rep_email).
    """
    tier = assign_tier(score)
    rep = assign_rep(tier)
    logger.info("Routed score=%d → tier=%s, rep=%s", score, tier, rep)
    return tier, rep
