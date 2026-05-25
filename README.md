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

## Setup

Requires Python 3.11+.

```sh
pip install -r requirements.txt
cp .env.example .env   # fill in values
```

Run the database migration (requires direct connection string):

```sh
psql $LEAD_PIPELINE_DATABASE_URL_DIRECT -f migrations/001_create_leads_schema.sql
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude scoring | `sk-ant-...` |
| `LEAD_PIPELINE_DATABASE_URL` | Neon pooled connection string | `postgresql://user:pass@host/leads` |
| `LEAD_PIPELINE_DATABASE_URL_DIRECT` | Neon direct connection (DDL only) | `postgresql://user:pass@host/leads` |
| `GMAIL_SENDER` | Gmail address for sending alerts | `you@gmail.com` |
| `GMAIL_APP_PASSWORD` | Gmail app password (not your login password) | 16-char app password |
| `ALERT_RECIPIENT` | Where to send hot lead alerts and weekly reports | `team@company.com` |
| `INDUSTRY_CONTEXT` | Client-specific context passed to the scoring prompt | `business funding lender` |
| `REP_POOL` | Comma-separated rep emails for round-robin assignment | `rep1@co.com,rep2@co.com` |

## How to Run

**Batch mode** — process a CSV file:
```sh
python main.py --mode batch --file data/sample_leads.csv
```

**Webhook mode** — start the FastAPI server on port 8000:
```sh
python main.py --mode webhook

# Send a lead via curl
curl -X POST http://localhost:8000/leads \
  -H "Content-Type: application/json" \
  -d '{"email": "test@company.com", "name": "Test User", "source": "facebook_ad", "company": "ACME Corp"}'
```

**Report mode** — send weekly digest email:
```sh
python main.py --mode report
```

## How to Test

```sh
pip install -r requirements-dev.txt
python -m pytest
```
