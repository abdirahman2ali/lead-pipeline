import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.ingestor import Lead

logger = logging.getLogger(__name__)

_TIER_COLOR = {"hot": "#C0392B", "warm": "#E67E22", "cold": "#7F8C8D"}


def _alert_html(lead: Lead, score: int, tier: str, rep: str, reasoning: str, signals: list[str]) -> str:
    color = _TIER_COLOR.get(tier, "#7F8C8D")
    signals_html = "".join(
        f'<span style="display:inline-block;margin:2px 4px 2px 0;padding:3px 10px;background:#F0F0F0;color:#555;border-radius:12px;font-size:12px;">{s}</span>'
        for s in signals
    )

    def row(label: str, value: str) -> str:
        if not value:
            return ""
        return f"""
        <tr>
          <td style="padding:4px 12px 4px 0;color:#7F8C8D;font-size:12px;white-space:nowrap;vertical-align:top;">{label}</td>
          <td style="padding:4px 0;color:#2C3E50;font-size:13px;">{value}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F2F3F4;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#F2F3F4;padding:24px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">
        <tr>
          <td style="background:#1A252F;padding:20px 24px;border-radius:6px 6px 0 0;border-left:5px solid {color};">
            <div style="color:#fff;font-size:17px;font-weight:700;">Hot Lead Alert</div>
            <div style="color:#95A5A6;font-size:12px;margin-top:4px;">Score {score}/100 &middot; Tier: {tier.upper()} &middot; Assigned to {rep}</div>
          </td>
        </tr>
        <tr>
          <td style="background:#fff;padding:20px 24px;border-radius:0 0 6px 6px;">
            <table cellpadding="0" cellspacing="0">
              {row("Name", lead.name)}
              {row("Email", lead.email)}
              {row("Phone", lead.phone or "")}
              {row("Company", lead.company or "")}
              {row("Source", lead.source)}
            </table>
            <div style="margin-top:12px;padding:10px 12px;background:#FEF9E7;border-left:3px solid {color};font-size:12px;color:#555;">
              <strong>Why:</strong> {reasoning}
            </div>
            <div style="margin-top:10px;">{signals_html}</div>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_hot_lead_alert(lead: Lead, score: int, tier: str, rep: str, reasoning: str, signals: list[str]) -> None:
    """Send an immediate email alert for a hot lead.

    Args:
        lead: The normalized Lead.
        score: Integer score 1-100.
        tier: Tier string ('hot', 'warm', 'cold').
        rep: Assigned rep email.
        reasoning: Claude's scoring rationale.
        signals: List of signal strings from scoring.
    """
    smtp_user = os.environ.get("GMAIL_SENDER", "")
    smtp_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    alert_recipient = os.environ.get("ALERT_RECIPIENT", smtp_user)

    if not smtp_user or not smtp_password:
        logger.warning("GMAIL_SENDER or GMAIL_APP_PASSWORD not set — skipping hot lead alert")
        return

    html = _alert_html(lead, score, tier, rep, reasoning, signals)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Hot Lead: {lead.name} ({lead.company or lead.source}) — Score {score}/100"
    msg["From"] = smtp_user
    msg["To"] = alert_recipient
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, alert_recipient, msg.as_string())
        logger.info("Hot lead alert sent for %s (score=%d)", lead.email, score)
    except Exception as e:
        logger.error("Failed to send hot lead alert for %s: %s", lead.email, e)
