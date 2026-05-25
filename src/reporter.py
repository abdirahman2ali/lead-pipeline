import logging
import os
import smtplib
from datetime import date, datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


def _engine():
    url = os.environ["LEAD_PIPELINE_DATABASE_URL"]
    return create_engine(url, poolclass=NullPool)


def _fetch_stats(since: Optional[datetime] = None) -> dict:
    """Query pipeline.leads and pipeline.events for weekly metrics."""
    since = since or (datetime.now(timezone.utc) - timedelta(days=7))

    with _engine().connect() as conn:
        totals = conn.execute(text("""
            select
                count(*) as total,
                count(*) filter (where tier = 'hot') as hot,
                count(*) filter (where tier = 'warm') as warm,
                count(*) filter (where tier = 'cold') as cold,
                round(avg(score)) as avg_score
            from pipeline.leads
            where created_at >= :since
        """), {"since": since}).fetchone()

        by_source = conn.execute(text("""
            select source, count(*) as cnt
            from pipeline.leads
            where created_at >= :since
            group by source
            order by cnt desc
        """), {"since": since}).fetchall()

        sla = conn.execute(text("""
            select
                count(*) filter (where tier = 'hot') as hot_total,
                count(*) filter (where tier = 'hot' and speed_to_contact_min is not null and speed_to_contact_min <= 5) as hot_within_sla,
                round(avg(speed_to_contact_min) filter (where tier = 'hot'), 1) as avg_hot_speed,
                round(avg(speed_to_contact_min) filter (where tier = 'warm'), 1) as avg_warm_speed
            from pipeline.leads
            where created_at >= :since
        """), {"since": since}).fetchone()

    return {
        "total": totals.total or 0,
        "hot": totals.hot or 0,
        "warm": totals.warm or 0,
        "cold": totals.cold or 0,
        "avg_score": totals.avg_score or 0,
        "by_source": [(r.source, r.cnt) for r in by_source],
        "hot_total": sla.hot_total or 0,
        "hot_within_sla": sla.hot_within_sla or 0,
        "avg_hot_speed": sla.avg_hot_speed,
        "avg_warm_speed": sla.avg_warm_speed,
    }


def _build_html(stats: dict, since: datetime) -> str:
    run_date = date.today().strftime("%B %d, %Y")
    sla_pct = (
        round(stats["hot_within_sla"] / stats["hot_total"] * 100)
        if stats["hot_total"] > 0
        else "N/A"
    )
    sla_display = f"{sla_pct}%" if isinstance(sla_pct, int) else sla_pct

    source_rows = "".join(
        f'<tr><td style="padding:4px 12px 4px 0;color:#7F8C8D;font-size:12px;">{src}</td>'
        f'<td style="font-size:13px;color:#2C3E50;">{cnt}</td></tr>'
        for src, cnt in stats["by_source"]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F2F3F4;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#F2F3F4;padding:24px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

        <tr>
          <td style="background:#1A252F;padding:24px 28px;border-radius:6px 6px 0 0;">
            <div style="color:#fff;font-size:18px;font-weight:700;">Lead Pipeline — Weekly Report</div>
            <div style="color:#95A5A6;font-size:12px;margin-top:4px;">Week ending {run_date} &middot; {stats["total"]} leads processed</div>
          </td>
        </tr>

        <tr>
          <td style="background:#fff;padding:16px 28px;border-bottom:1px solid #E8E8E8;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td align="center" style="padding:8px;border-right:1px solid #E8E8E8;">
                  <div style="font-size:26px;font-weight:700;color:#C0392B;">{stats["hot"]}</div>
                  <div style="font-size:11px;color:#7F8C8D;letter-spacing:0.5px;">HOT</div>
                </td>
                <td align="center" style="padding:8px;border-right:1px solid #E8E8E8;">
                  <div style="font-size:26px;font-weight:700;color:#E67E22;">{stats["warm"]}</div>
                  <div style="font-size:11px;color:#7F8C8D;letter-spacing:0.5px;">WARM</div>
                </td>
                <td align="center" style="padding:8px;border-right:1px solid #E8E8E8;">
                  <div style="font-size:26px;font-weight:700;color:#7F8C8D;">{stats["cold"]}</div>
                  <div style="font-size:11px;color:#7F8C8D;letter-spacing:0.5px;">COLD</div>
                </td>
                <td align="center" style="padding:8px;">
                  <div style="font-size:26px;font-weight:700;color:#2980B9;">{stats["avg_score"]}</div>
                  <div style="font-size:11px;color:#7F8C8D;letter-spacing:0.5px;">AVG SCORE</div>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <tr>
          <td style="background:#fff;padding:16px 28px;border-bottom:1px solid #E8E8E8;">
            <div style="font-size:13px;font-weight:700;color:#7F8C8D;letter-spacing:0.8px;margin-bottom:10px;text-transform:uppercase;">Speed-to-Lead SLA</div>
            <table cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding:4px 12px 4px 0;color:#7F8C8D;font-size:12px;">Hot leads contacted within 5 min</td>
                <td style="font-size:13px;font-weight:700;color:#C0392B;">{sla_display}</td>
              </tr>
              <tr>
                <td style="padding:4px 12px 4px 0;color:#7F8C8D;font-size:12px;">Avg speed-to-contact (hot)</td>
                <td style="font-size:13px;color:#2C3E50;">{stats["avg_hot_speed"] or "—"} min</td>
              </tr>
              <tr>
                <td style="padding:4px 12px 4px 0;color:#7F8C8D;font-size:12px;">Avg speed-to-contact (warm)</td>
                <td style="font-size:13px;color:#2C3E50;">{stats["avg_warm_speed"] or "—"} min</td>
              </tr>
            </table>
          </td>
        </tr>

        <tr>
          <td style="background:#fff;padding:16px 28px;border-radius:0 0 6px 6px;">
            <div style="font-size:13px;font-weight:700;color:#7F8C8D;letter-spacing:0.8px;margin-bottom:10px;text-transform:uppercase;">Leads by Source</div>
            <table cellpadding="0" cellspacing="0">{source_rows}</table>
          </td>
        </tr>

        <tr>
          <td style="padding:16px 0;text-align:center;">
            <div style="font-size:11px;color:#AAB7B8;">Lead Pipeline &middot; Automated weekly digest</div>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_weekly_report(since: Optional[datetime] = None) -> None:
    """Fetch pipeline stats and email a weekly digest.

    Args:
        since: Start of reporting window (default: 7 days ago).
    """
    smtp_user = os.environ.get("GMAIL_SENDER", "")
    smtp_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    alert_recipient = os.environ.get("ALERT_RECIPIENT", smtp_user)

    if not smtp_user or not smtp_password:
        logger.warning("GMAIL_SENDER or GMAIL_APP_PASSWORD not set — skipping weekly report")
        return

    since = since or (datetime.now(timezone.utc) - timedelta(days=7))
    stats = _fetch_stats(since)

    if stats["total"] == 0:
        logger.info("No leads in the last 7 days — skipping weekly report")
        return

    html = _build_html(stats, since)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Lead Pipeline Weekly: {stats['total']} leads, {stats['hot']} hot"
    msg["From"] = smtp_user
    msg["To"] = alert_recipient
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, alert_recipient, msg.as_string())
        logger.info("Weekly report sent to %s (%d leads)", alert_recipient, stats["total"])
    except Exception as e:
        logger.error("Failed to send weekly report: %s", e)
