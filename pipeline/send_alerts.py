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

def send_email_alert(df_predictions: pd.DataFrame):
    """
    Filters the top predictions and sends an email alert.
    """
    sender_email = get_secret("SENDER_EMAIL")
    sender_password = get_secret("SENDER_PASSWORD")
    receiver_email = get_secret("RECEIVER_EMAIL")

    if not sender_email or not sender_password or not receiver_email:
        logger.warning("Email credentials missing. Skipping email alert.")
        return

    # Filter for high confidence signals
    if not df_predictions.empty:
        # Assuming df has 'ticker', 'direction', 'confidence', 'strength'
        strong_signals = df_predictions[df_predictions['strength'] == 'strong'].copy()
        
        # Sort by confidence
        strong_signals = strong_signals.sort_values(by="confidence", ascending=False)
    else:
        strong_signals = pd.DataFrame()

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    # Construct Email Body
    html_content = f"""
    <html>
    <head></head>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #00D4AA;">MarketPulse AI - Daily Intelligence Report</h2>
        <p><b>Date:</b> {today_str}</p>
        <p>The AI pipeline has finished running for the day. Here are the strongest quantitative signals:</p>
    """

    if strong_signals.empty:
        html_content += "<p><i>No 'strong' confidence signals detected today. The market is highly unpredictable right now.</i></p>"
    else:
        html_content += """
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%; max-width: 600px;">
            <tr style="background-color: #f2f2f2;">
                <th>Ticker</th>
                <th>Direction</th>
                <th>Confidence</th>
            </tr>
        """
        for _, row in strong_signals.iterrows():
            ticker = row['ticker']
            direction = row['direction']
            confidence = f"{row['confidence']:.1%}"
            
            color = "green" if direction.upper() == "BULLISH" else "red"
            
            html_content += f"""
            <tr>
                <td><b>{ticker}</b></td>
                <td style="color: {color}; font-weight: bold;">{direction}</td>
                <td>{confidence}</td>
            </tr>
            """
        html_content += "</table>"

    html_content += """
        <br>
        <p>View the full details on your live dashboard: <a href="https://marketpulseai-ldtbr3bebbybb8njzf6pmj.streamlit.app/">MarketPulse AI Dashboard</a></p>
        <hr>
        <p style="font-size: 12px; color: #777;"><i>Disclaimer: MarketPulse AI is an educational research project. These signals are statistical indicators and do not constitute financial advice.</i></p>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"📈 MarketPulse AI Alert: {len(strong_signals)} Strong Signals ({today_str})"
    msg['From'] = f"MarketPulse AI <{sender_email}>"
    msg['To'] = receiver_email

    msg.attach(MIMEText(html_content, "html"))

    try:
        logger.info(f"Connecting to Gmail SMTP to send alert to {receiver_email}...")
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        logger.info("Email alert sent successfully!")
    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")

if __name__ == "__main__":
    # For testing purposes
    test_df = pd.DataFrame({
        "ticker": ["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS"],
        "direction": ["BULLISH", "BEARISH", "BULLISH"],
        "confidence": [0.85, 0.72, 0.45],
        "strength": ["strong", "strong", "moderate"]
    })
    send_email_alert(test_df)
