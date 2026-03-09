"""
E-posta Kanalı — POP3 okuma + AI yanıt + SMTP gönderim.

Her tenant kendi POP3 kutusunu tanımlayabilir. Cron ile çağrılır:
    POST /api/cron/email-poll?key=SECRET

Tenant ayarlarında tanımlanması gereken alanlar (settings_ai veya API patch ile):
    email_pop3_host       : pop.firma.com
    email_pop3_port       : 995  (SSL) veya 110
    email_pop3_ssl        : true
    email_pop3_user       : destek@firma.com
    email_pop3_password   : xxxxxxx
    email_smtp_host       : smtp.firma.com   (yoksa sistem SMTP kullanılır)
    email_smtp_port       : 587
    email_smtp_user       : destek@firma.com
    email_smtp_password   : xxxxxxx
    email_smtp_from       : destek@firma.com
    email_reply_signature : "\n\n---\nEmare Asistan tarafından gönderilmiştir."
"""
from __future__ import annotations

import asyncio
import email
import email.header
import imaplib
import json
import logging
import os
import poplib
import re
import smtplib
import ssl
import textwrap
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid, parseaddr
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models import Tenant
from models.database import AsyncSessionLocal
from services.core.tenant import get_tenant_settings

logger = logging.getLogger(__name__)

IMPORTANT_KEYWORDS = {
    "acil", "urgent", "ivedi", "şikayet", "sikayet", "iptal", "iade",
    "ödeme", "odeme", "hukuk", "yasal", "tehdit", "problem", "sorun",
    "çalışmıyor", "calismiyor", "arıza", "ariza", "hata", "uyarı", "uyari",
}

SOCIAL_KEYWORDS = {
    "duyuru", "announcement", "bulten", "bülten", "kampanya", "newsletter",
    "social", "sosyal", "instagram", "facebook", "linkedin", "twitter",
    "x.com", "tiktok", "youtube", "post", "icerik", "içerik",
}


def _categorize_inbound_email(subject: str, body: str, sender: str) -> tuple[str, bool]:
    """Gelen e-postayı kategoriye ayırır ve önem derecesi döndürür."""
    text = f"{subject or ''}\n{body or ''}\n{sender or ''}".lower()

    if any(k in text for k in IMPORTANT_KEYWORDS):
        return "onemli", True

    if any(k in text for k in SOCIAL_KEYWORDS):
        return "sosyal_duyuru", False

    if sender and any(k in sender.lower() for k in ("noreply", "no-reply", "mailer-daemon")):
        return "otomatik_bildirim", False

    return "genel", False

# ──────────────────────────────────────────────────────────────────────────────

_SEEN_DIR = Path(__file__).resolve().parent.parent / "data" / "tenants"


def _seen_path(slug: str) -> Path:
    return _SEEN_DIR / slug / "email_seen_uids.json"


def _load_seen(slug: str) -> set[str]:
    p = _seen_path(slug)
    if not p.exists():
        return set()
    try:
        return set(json.loads(p.read_text()))
    except Exception:
        return set()


def _save_seen(slug: str, uids: set[str]) -> None:
    p = _seen_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sorted(uids)))


# ──────────────────────────────────────────────────────────────────────────────
# E-posta ayrıştırma
# ──────────────────────────────────────────────────────────────────────────────

def _decode_header_value(val: str) -> str:
    """RFC 2047 kodlu header değerini unicode'a çevir."""
    parts = []
    for chunk, charset in email.header.decode_header(val):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(chunk)
    return "".join(parts)


def _extract_plain_body(msg: email.message.Message) -> str:
    """text/plain body'yi çıkar; yoksa text/html'den tag'leri soy."""
    body = ""
    for part in msg.walk():
        ctype = part.get_content_type()
        disp = part.get("Content-Disposition", "")
        if "attachment" in disp:
            continue
        if ctype == "text/plain":
            charset = part.get_content_charset() or "utf-8"
            payload = part.get_payload(decode=True)
            if payload:
                body = payload.decode(charset, errors="replace")
                break
        elif ctype == "text/html" and not body:
            charset = part.get_content_charset() or "utf-8"
            payload = part.get_payload(decode=True)
            if payload:
                html = payload.decode(charset, errors="replace")
                # Basit HTML → metin: tag'leri kaldır
                body = re.sub(r"<[^>]+>", " ", html)
                body = re.sub(r"\s{2,}", "\n", body).strip()

    # Alıntılanmış kısımları kaldır (> ile başlayan satırlar ve "---- Original" vb.)
    lines = body.splitlines()
    clean: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(">"):
            break
        if re.match(r"^[-=_]{3,}.*original.*message", stripped, re.IGNORECASE):
            break
        if re.match(r"^On .+ wrote:$", stripped, re.IGNORECASE):
            break
        clean.append(line)
    return "\n".join(clean).strip()


def _parse_email(raw: bytes) -> dict | None:
    """Ham e-posta baytlarını ayrıştır, sözlük döndür."""
    try:
        msg = email.message_from_bytes(raw)
        sender_full = _decode_header_value(msg.get("From", ""))
        sender_name, sender_addr = parseaddr(sender_full)
        sender_addr = sender_addr.strip().lower()
        if not sender_addr or "@" not in sender_addr:
            return None
        subject = _decode_header_value(msg.get("Subject", "(Konu yok)"))
        msg_id = (msg.get("Message-ID") or "").strip()
        body = _extract_plain_body(msg)
        if not body:
            return None
        return {
            "from_addr": sender_addr,
            "from_name": sender_name or sender_addr.split("@")[0],
            "subject": subject,
            "msg_id": msg_id,
            "body": body[:4000],  # Çok uzun mailleri kırp
            "reply_to": (msg.get("Reply-To") or sender_full),
            "in_reply_to": (msg.get("In-Reply-To") or ""),
            "references": (msg.get("References") or ""),
        }
    except Exception as e:
        logger.warning("E-posta ayrıştırma hatası: %s", e)
        return None


# ──────────────────────────────────────────────────────────────────────────────
# POP3 okuma
# ──────────────────────────────────────────────────────────────────────────────

def _pop3_fetch_new(
    host: str,
    port: int,
    user: str,
    password: str,
    use_ssl: bool,
    seen_uids: set[str],
) -> list[tuple[str, bytes]]:
    """
    POP3 kutusundaki yeni mesajları getir.
    Dönen liste: [(uid, raw_bytes), ...]
    """
    try:
        if use_ssl:
            ctx = ssl.create_default_context()
            conn = poplib.POP3_SSL(host, port, context=ctx, timeout=30)
        else:
            conn = poplib.POP3(host, port, timeout=30)

        conn.user(user)
        conn.pass_(password)

        # UIDL destekleniyorsa benzersiz id al
        try:
            uidl_resp = conn.uidl()
            # uidl_resp[1] -> [b"1 uniqueid1", b"2 uniqueid2", ...]
            uid_map: dict[str, str] = {}  # msg_num -> uid
            for item in uidl_resp[1]:
                parts = item.decode("utf-8", errors="replace").split()
                if len(parts) >= 2:
                    uid_map[parts[0]] = parts[1]
        except poplib.error_proto:
            # UIDL desteklenmiyor — indeks numaralarını uid gibi kullan
            num_msgs = len(conn.list()[1])
            uid_map = {str(i): f"idx-{i}" for i in range(1, num_msgs + 1)}

        results: list[tuple[str, bytes]] = []
        for num, uid in uid_map.items():
            if uid in seen_uids:
                continue
            try:
                raw_lines = conn.retr(int(num))[1]
                raw = b"\r\n".join(raw_lines)
                results.append((uid, raw))
            except Exception as e:
                logger.warning("POP3 mesaj indirme hatası (num=%s): %s", num, e)

        conn.quit()
        return results

    except Exception as e:
        logger.error("POP3 bağlantı hatası (%s@%s:%s): %s", user, host, port, e)
        return []


# ──────────────────────────────────────────────────────────────────────────────
# SMTP gönderim
# ──────────────────────────────────────────────────────────────────────────────

def _smtp_send_reply(
    host: str,
    port: int,
    user: str,
    password: str,
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
    in_reply_to: str = "",
    references: str = "",
    signature: str = "",
) -> bool:
    """SMTP ile e-posta gönder. Başarı bool döner."""
    try:
        full_body = body + signature

        msg = MIMEMultipart("alternative")
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg["Subject"] = subject if subject.startswith("Re:") else f"Re: {subject}"
        msg["Message-ID"] = make_msgid()
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
            refs = f"{references} {in_reply_to}".strip() if references else in_reply_to
            msg["References"] = refs

        msg.attach(MIMEText(full_body, "plain", "utf-8"))

        # HTML versiyonu — satır sonlarını <br> yap
        html_body = full_body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html_body = html_body.replace("\n", "<br>\n")
        html_part = (
            f"<html><body style='font-family:sans-serif;font-size:14px;'>"
            f"{html_body}</body></html>"
        )
        msg.attach(MIMEText(html_part, "html", "utf-8"))

        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(user, password)
            server.sendmail(from_addr, to_addr, msg.as_string())
        return True

    except Exception as e:
        logger.error("SMTP gönderim hatası (%s → %s): %s", from_addr, to_addr, e)
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Ana çalışma döngüsü
# ──────────────────────────────────────────────────────────────────────────────

async def _process_tenant_inbox(tenant: Tenant, settings: dict) -> int:
    """Bir tenant'ın gelen kutusunu işle. İşlenen e-posta sayısını döndür."""

    pop3_host = (settings.get("email_pop3_host") or "").strip()
    pop3_user = (settings.get("email_pop3_user") or "").strip()
    pop3_pass = (settings.get("email_pop3_password") or "").strip()
    if not pop3_host or not pop3_user or not pop3_pass:
        return 0

    pop3_port = int(settings.get("email_pop3_port") or 995)
    pop3_ssl = str(settings.get("email_pop3_ssl", "true")).lower() not in ("0", "false", "no")

    # SMTP — tenant'ın kendi SMTP'si yoksa sistem SMTP
    sys_cfg = get_settings()
    smtp_host = (settings.get("email_smtp_host") or sys_cfg.smtp_host or "").strip()
    smtp_port = int(settings.get("email_smtp_port") or sys_cfg.smtp_port or 587)
    smtp_user = (settings.get("email_smtp_user") or sys_cfg.smtp_user or "").strip()
    smtp_pass = (settings.get("email_smtp_password") or sys_cfg.smtp_password or "").strip()
    smtp_from = (settings.get("email_smtp_from") or smtp_user or pop3_user).strip()
    signature = settings.get(
        "email_reply_signature",
        "\n\n---\nBu yanıt Emare Asistan tarafından otomatik oluşturulmuştur.",
    )

    if not smtp_host or not smtp_user:
        logger.warning("Tenant %s: SMTP yapılandırılmamış, e-posta cevaplanamaz.", tenant.id)
        return 0

    seen = _load_seen(tenant.slug)
    new_msgs = await asyncio.to_thread(
        _pop3_fetch_new, pop3_host, pop3_port, pop3_user, pop3_pass, pop3_ssl, seen
    )

    if not new_msgs:
        return 0

    processed = 0
    async with AsyncSessionLocal() as db:
        from integrations import ChatHandler
        handler = ChatHandler(db)

        for uid, raw in new_msgs:
            parsed = _parse_email(raw)
            if not parsed:
                seen.add(uid)
                continue

            # Otomatik sistemlerden gelen döngüsel mailler
            sender = parsed["from_addr"]
            if any(kw in sender for kw in ("noreply", "no-reply", "donotreply", "mailer-daemon")):
                seen.add(uid)
                continue

            category, is_important = _categorize_inbound_email(
                parsed.get("subject", ""),
                parsed.get("body", ""),
                parsed.get("from_addr", ""),
            )

            if is_important:
                try:
                    from services.notifications.user_notifier import notify_important_message

                    await notify_important_message(
                        db=db,
                        tenant_id=tenant.id,
                        tenant_name=tenant.name or tenant.slug or "Tenant",
                        source="e-posta",
                        sender=parsed.get("from_addr", ""),
                        subject=parsed.get("subject", ""),
                        preview=parsed.get("body", "")[:220],
                    )
                except Exception as e:
                    logger.warning("Önemli e-posta bildirimi atlanıyor (tenant=%s): %s", tenant.id, e)

            # Konu + gövde birleştir → ChatHandler'a gönder
            user_text = (
                f"[Kategori: {category}]\n"
                f"[Konu: {parsed['subject']}]\n\n"
                f"{parsed['body']}"
            )

            try:
                response = await handler.process_message(
                    platform="email",
                    user_id=sender,
                    message_text=user_text,
                    conversation_history=[],
                    customer_name=parsed["from_name"],
                    tenant_id=tenant.id,
                )
            except Exception as e:
                logger.error("Tenant %s e-posta işleme hatası (%s): %s", tenant.id, sender, e)
                seen.add(uid)
                continue

            reply_text = (response.get("text") or "").strip()
            if not reply_text:
                seen.add(uid)
                continue

            sent = await asyncio.to_thread(
                _smtp_send_reply,
                smtp_host, smtp_port, smtp_user, smtp_pass,
                smtp_from, sender,
                parsed["subject"], reply_text,
                parsed["in_reply_to"] or parsed["msg_id"],
                parsed["references"],
                signature,
            )

            if sent:
                logger.info(
                    "Tenant %s: e-posta yanıtlandı → %s (konu: %s)",
                    tenant.id, sender, parsed["subject"][:60],
                )
                processed += 1
            else:
                logger.warning("Tenant %s: SMTP gönderim başarısız → %s", tenant.id, sender)

            # Başarılı ya da başarısız — bir daha işleme alma
            seen.add(uid)

    _save_seen(tenant.slug, seen)
    return processed


async def poll_all_tenants() -> dict[str, int]:
    """
    Tüm aktif tenantların e-posta kutularını tara.
    Cron endpoint'inden çağrılır.
    Döner: {tenant_slug: işlenen_sayı}
    """
    results: dict[str, int] = {}
    async with AsyncSessionLocal() as db:
        q = await db.execute(select(Tenant).where(Tenant.status == "active"))
        tenants = q.scalars().all()

    for tenant in tenants:
        try:
            settings = await get_tenant_settings(tenant.id)
            if not settings.get("email_pop3_host"):
                continue
            count = await _process_tenant_inbox(tenant, settings)
            results[tenant.slug] = count
        except Exception as e:
            logger.exception("Tenant %s e-posta poll hatası: %s", tenant.id, e)
            results[tenant.slug] = -1

    return results
