import argparse
import csv
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".claude" / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_batch(file_path: str) -> None:
    from src import crm_sync, dedup_store, ingestor, notifier, router, scorer

    dedup_store.init_store()

    path = Path(file_path)
    if not path.exists():
        logger.error("File not found: %s", file_path)
        sys.exit(1)

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    logger.info("Loaded %d rows from %s", len(rows), file_path)
    processed = 0
    skipped = 0

    for row in rows:
        try:
            lead = ingestor.normalize(row)
        except ValueError as e:
            logger.warning("Skipping invalid row: %s", e)
            skipped += 1
            continue

        is_dup = dedup_store.is_duplicate(lead)

        lead_id = dedup_store.upsert(lead)
        crm_sync.log_event(lead_id, "ingested", {"source": lead.source, "duplicate": is_dup})

        if is_dup:
            crm_sync.log_event(lead_id, "deduped")
            logger.info("Duplicate — skipping scoring for %s", lead.email)
            skipped += 1
            continue

        score, reasoning, signals = scorer.score_lead(lead)
        tier, rep = router.route(score)

        dedup_store.upsert(lead, score=score, tier=tier, assigned_to=rep)
        crm_sync.log_event(lead_id, "scored", {"score": score, "reasoning": reasoning, "signals": signals})
        crm_sync.log_event(lead_id, "routed", {"tier": tier, "assigned_to": rep})

        if tier == "hot":
            notifier.send_hot_lead_alert(lead, score, tier, rep, reasoning, signals)

        processed += 1

    logger.info("Done: %d processed, %d skipped (duplicates or invalid)", processed, skipped)


def run_webhook() -> None:
    import uvicorn
    from api import app
    uvicorn.run(app, host="0.0.0.0", port=8000)


def run_report() -> None:
    from src.reporter import send_weekly_report
    send_weekly_report()


def main() -> None:
    parser = argparse.ArgumentParser(description="Lead pipeline CLI")
    parser.add_argument(
        "--mode",
        choices=["batch", "webhook", "report"],
        required=True,
        help="batch: process a CSV; webhook: start FastAPI server; report: send weekly digest",
    )
    parser.add_argument("--file", help="CSV file path (required for --mode batch)")
    args = parser.parse_args()

    if args.mode == "batch":
        if not args.file:
            parser.error("--file is required when --mode is batch")
        run_batch(args.file)
    elif args.mode == "webhook":
        run_webhook()
    elif args.mode == "report":
        run_report()


if __name__ == "__main__":
    main()
