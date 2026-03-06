"""E-posta gönderim servisi - kayıt onayı, bildirimler
Firma SMTP (Entegrasyonlar > E-posta) tanımlıysa kullanılır, yoksa .env SMTP.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

from config import get_settings


def _get_smtp_config(tenant_id: int | None = None) -> dict | None:
    """
    SMTP yapılandırması döndür. tenant_id verilirse get_module_api_settings ile
    firma e-posta ayarları alınır (async olmadığı için None döner - async sürüm kullanılmalı).
    Senkron kullanımda sadece global config.
    """
    settings = get_settings()
    return {
        "host": settings.smtp_host or "",
        "port": settings.smtp_port or 587,
        "user": settings.smtp_user or "",
        "password": settings.smtp_password or "",
        "from_addr": settings.smtp_from or "",
        "from_name": "Emare Asistan",
    }


async def get_smtp_config_for_tenant(tenant_id: int) -> dict | None:
    """
    Firma SMTP ayarlarını döndür. Firma tanımlı değilse global .env kullanılır.
    Returns: { host, port, user, password, from_addr, from_name } veya None (yapılandırılmamışsa)
    """
    from services.core.tenant import get_module_api_settings

    cfg = await get_module_api_settings(tenant_id, "email")
    host = (cfg.get("smtp_host") or "").strip()
    user = (cfg.get("smtp_user") or "").strip()
    if not host and not user:
        settings = get_settings()
        host = (settings.smtp_host or "").strip()
        user = (settings.smtp_user or "").strip()
    if not host or not user:
        return None
    port = int(cfg.get("smtp_port") or get_settings().smtp_port or 587)
    from_addr = (cfg.get("smtp_from") or user or get_settings().smtp_from or "").strip()
    from_name = (cfg.get("smtp_from_name") or "").strip() or "Emare Asistan"
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": (cfg.get("smtp_password") or "").strip() or get_settings().smtp_password or "",
        "from_addr": from_addr,
        "from_name": from_name,
    }


def _send_with_config(config: dict, to_email: str, subject: str, html_body: str) -> bool:
    """Verilen SMTP config ile e-posta gönder"""
    if not config or not config.get("host") or not config.get("user"):
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((config.get("from_name", "Emare Asistan"), config.get("from_addr", "")))
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    try:
        with smtplib.SMTP(config["host"], config["port"]) as server:
            server.starttls()
            server.login(config["user"], config.get("password") or "")
            server.sendmail(config["from_addr"], to_email, msg.as_string())
        return True
    except Exception:
        return False


def send_confirmation_email(to_email: str, confirm_url: str, tenant_name: str, smtp_config: dict | None = None) -> bool:
    """
    Kayıt onay linki e-postası gönder.
    smtp_config verilirse onu kullanır (async get_smtp_config_for_tenant'dan); yoksa global .env.
    """
    config = smtp_config or _get_smtp_config()
    if not config or not config.get("host") or not config.get("user"):
        return False

    subject = "Emare Asistan - Hesabınızı Onaylayın"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: 'Segoe UI', system-ui, sans-serif; line-height: 1.6; color: #334155; max-width: 600px; margin: 0 auto; padding: 1.5rem;">
      <h2 style="color: #1e3a5f;">Emare Asistan</h2>
      <p>Merhaba,</p>
      <p><strong>{tenant_name}</strong> için kaydınızı tamamlamak üzere aşağıdaki linke tıklayın:</p>
      <p style="margin: 1.5rem 0;">
        <a href="{confirm_url}" style="display: inline-block; background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%); color: #fff; padding: 0.75rem 1.5rem; text-decoration: none; border-radius: 8px; font-weight: 500;">Hesabı Onayla</a>
      </p>
      <p style="font-size: 0.875rem; color: #64748b;">Link 24 saat içinde geçerlidir.</p>
      <p style="font-size: 0.875rem; color: #64748b;">Bu e-postayı siz talep etmediyseniz lütfen dikkate almayın.</p>
      <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 2rem 0;">
      <p style="font-size: 0.75rem; color: #94a3b8;">Emare Asistan</p>
    </body>
    </html>
    """

    return _send_with_config(config, to_email, subject, html)
