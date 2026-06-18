import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
import pandas as pd
import logging
from config.settings import get_secret

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dashboard URL (update if your Streamlit URL changes)
DASHBOARD_URL = "https://marketpulseai-ldtbr3bebbybb8njzf6pmj.streamlit.app/"


def send_email_alert(df_predictions: pd.DataFrame = None):
    """
    Filters the top predictions and sends an email alert.

    Args:
        df_predictions: DataFrame with columns matching the predictions table
                        (signal_strength, predicted_direction, final_confidence, ticker)
                        If None or empty, attempts to fetch today's data from Supabase.
    """
    sender_email    = get_secret("SENDER_EMAIL")
    sender_password = get_secret("SENDER_PASSWORD")
    receiver_email  = get_secret("RECEIVER_EMAIL")

    if sender_email: sender_email = sender_email.strip()
    if sender_password: sender_password = sender_password.strip()
    if receiver_email: receiver_email = receiver_email.strip()

    if not sender_email or not sender_password or not receiver_email:
        logger.warning("Email credentials missing (SENDER_EMAIL / SENDER_PASSWORD / RECEIVER_EMAIL). Skipping email alert.")
        return

    # ── If no DataFrame provided, pull today's predictions from Supabase ──────
    if df_predictions is None or df_predictions.empty:
        logger.info("No predictions DataFrame provided — fetching from Supabase...")
        try:
            from config.settings import SUPABASE_URL, SUPABASE_KEY
            from supabase import create_client
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            sb  = create_client(SUPABASE_URL, SUPABASE_KEY)
            res = sb.table("predictions").select("*").eq("date", today).execute()
            df_predictions = pd.DataFrame(res.data) if res.data else pd.DataFrame()
            logger.info(f"  Fetched {len(df_predictions)} predictions from Supabase for {today}")
        except Exception as e:
            logger.warning(f"  Supabase fetch failed: {e}")
            df_predictions = pd.DataFrame()

    # ── Filter for strong signals using correct DB column names ───────────────
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if not df_predictions.empty and "signal_strength" in df_predictions.columns:
        top_signals = df_predictions.sort_values(
            by="final_confidence", ascending=False
        ).head(10).copy()
        n_strong = len(df_predictions[df_predictions["signal_strength"] == "strong"])
    else:
        top_signals = pd.DataFrame()
        n_strong = 0

    # ── Build HTML email body ─────────────────────────────────────────────────
    html_content = f"""
    <html>
    <head></head>
    <body style="font-family: Arial, sans-serif; color: #333; background-color: #f9f9f9;">
        <div style="max-width:620px;margin:auto;background:#fff;border-radius:10px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        <h2 style="color: #00D4AA; margin-top:0;">📈 MarketPulse AI — Daily Intelligence Report</h2>
        <p><b>Date:</b> {today_str} &nbsp;|&nbsp; <b>Signals source:</b> EOD Pipeline (3:45 PM IST)</p>
        <p>The AI pipeline has finished running for the day. Here are the top 10 highest-confidence signals:</p>
    """

    if top_signals.empty:
        html_content += "<p><i>⚠ No signals generated today. The market may be highly uncertain.</i></p>"
    else:
        html_content += """
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;max-width:580px;font-size:14px;">
            <tr style="background-color:#00D4AA;color:#fff;">
                <th>Ticker</th>
                <th>Direction</th>
                <th>Confidence</th>
                <th>Strength</th>
            </tr>
        """
        for _, row in top_signals.iterrows():
            ticker    = row.get("ticker", "—")
            direction = row.get("predicted_direction", "—")
            conf_val  = row.get("final_confidence", 0)
            strength  = row.get("signal_strength", "—")
            confidence = f"{float(conf_val):.1%}" if conf_val else "—"
            color = "#22c55e" if str(direction).lower() == "bullish" else "#ef4444"
            icon  = "⬆" if str(direction).lower() == "bullish" else "⬇"

            html_content += f"""
            <tr>
                <td><b>{ticker}</b></td>
                <td style="color:{color};font-weight:bold;">{icon} {direction.title()}</td>
                <td>{confidence}</td>
                <td>{strength.title() if strength else '—'}</td>
            </tr>
            """
        html_content += "</table>"

    html_content += f"""
        <br>
        <p>👉 View full details: <a href="{DASHBOARD_URL}" style="color:#00D4AA;">MarketPulse AI Dashboard</a></p>
        <hr>
        <p style="font-size:12px;color:#777;"><i>⚠ Disclaimer: MarketPulse AI is an educational research project.
        These signals are statistical indicators only and do not constitute financial advice.
        Not SEBI registered. Do not use for actual trading decisions.</i></p>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📈 MarketPulse AI: {n_strong} Strong Signal{'s' if n_strong != 1 else ''} — {today_str}"
    msg["From"]    = f"MarketPulse AI <{sender_email}>"
    msg["To"]      = receiver_email

    msg.attach(MIMEText(html_content, "html"))

    try:
        logger.info(f"Sending email alert → {receiver_email} ({n_strong} strong signals)...")
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        logger.info("✅ Email alert sent successfully!")
    except Exception as e:
        logger.error(f"❌ Failed to send email alert: {e}")


if __name__ == "__main__":
    # For testing: python -m pipeline.send_alerts
    send_email_alert()  # Will auto-fetch today's Supabase data

