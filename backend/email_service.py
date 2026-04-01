import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")
APP_URL = os.getenv("APP_URL", "http://localhost:9873")


def _send_email(to: str, subject: str, html_body: str) -> bool:
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS]):
        logger.warning("SMTP not configured, email not sent to %s", to)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM or SMTP_USER
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(msg["From"], [to], msg.as_string())
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False


def send_password_reset_email(to: str, token: str) -> bool:
    reset_url = f"{APP_URL}/reset-password?token={token}"
    html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
        <h2 style="color: #1f2937;">Abacus - Password Reset</h2>
        <p style="color: #4b5563;">You requested a password reset. Click the button below to set a new password:</p>
        <a href="{reset_url}"
           style="display: inline-block; padding: 12px 24px; background: #1f2937; color: #fff;
                  text-decoration: none; border-radius: 8px; font-weight: 600; margin: 16px 0;">
            Reset Password
        </a>
        <p style="color: #9ca3af; font-size: 14px;">
            This link expires in 15 minutes.<br>
            If you did not request this, you can safely ignore this email.
        </p>
    </div>
    """
    return _send_email(to, "Abacus - Password Reset", html)
