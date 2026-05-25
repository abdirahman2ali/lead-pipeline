# Lead Pipeline

End-to-end lead processing pipeline: ingest from any source (webhook or CSV), deduplicate, score with Claude AI, route to reps, and alert on hot leads. Designed for high-volume sales operations where speed-to-lead and data quality determine close rate.

## Architecture

```
Lead Source (webhook / CSV)
        ↓
   Normalize          — validate fields, format email + phone to E.164
        ↓
   Deduplicate        — Postgres check on email OR phone
        ↓
   AI Score (Claude)  — 1-100 score with intent signals and reasoning
        ↓
   Route              — tier (hot/warm/cold) + round-robin rep assignment
        ↓
   CRM Sync           — upsert to Postgres, append event log
        ↓
   Alert              — immediate email on hot leads (score ≥ 75)
        ↓
   Weekly Report      — volume, tier breakdown, speed-to-lead SLA
```

**Stack**: Python 3.11, FastAPI, SQLAlchemy, Neon Postgres, Claude API, GitHub Actions

