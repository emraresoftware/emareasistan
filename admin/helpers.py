"""
Admin paneli ortak yardımcılar - route modülleri ve routes.py buradan import eder.
"""
from __future__ import annotations
import json
import re
import smtplib
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.text import MIMEText
from email.utils import formataddr

import httpx
from fastapi import Request, HTTPException
from fastapi import UploadFile
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models.database import AsyncSessionLocal
from models import Conversation, Message, AuditLog, Tenant

from admin.common import get_tenant_id, _request_client_ip

PAGE_SIZE = 20


def _get_local_llm_status() -> dict:
    """Lokal yapay zeka durumunu kontrol et (online/offline/missing)."""
    settings = get_settings()
    enabled = bool(settings.local_llm_enabled)
    root = Path(__file__).resolve().parent.parent
    python_path = root / (settings.local_llm_python_bin or "").lstrip("./")
    script_path = root / (settings.local_llm_chat_script or "").lstrip("./")
    adapter_path = root / (settings.local_llm_adapter_path or "").lstrip("./")
    python_ok = python_path.exists()
    script_ok = script_path.exists()
    adapter_ok = adapter_path.exists()
    if not enabled:
        return {"status": "disabled", "label": "Kapalı", "enabled": False, "message": "LOCAL_LLM_ENABLED=false"}
    if not python_ok:
        return {"status": "missing", "label": "Eksik", "enabled": True, "message": f"Python bulunamadı: {python_path}"}
    if not script_ok:
        return {"status": "missing", "label": "Eksik", "enabled": True, "message": f"Chat script bulunamadı: {script_path}"}
    if not adapter_ok:
        return {"status": "missing", "label": "Eksik", "enabled": True, "message": f"LoRA adapter bulunamadı: {adapter_path}"}
    return {"status": "online", "label": "Online", "enabled": True, "message": "API koptuğunda fallback olarak devreye girer"}


async def get_enabled_modules_for_request(request: Request) -> set:
    """Request'e göre etkin modüller (template context için)"""
    from services.core.modules import get_enabled_modules
    tid = get_tenant_id(request)
    if tid is None:
        return set()
    return await get_enabled_modules(tid)


async def require_module(request: Request, module_id: str) -> None:
    """Modül etkin değilse 403 - route başında çağır"""
    from services.core.modules import is_module_enabled
    em = getattr(request.state, "enabled_modules", None) or set()
    if em and not is_module_enabled(em, module_id):
        raise HTTPException(403, detail=f"Bu özellik ({module_id}) bu firma için etkin değil.")


_LEAD_PHONE_RE = re.compile(r"\+?\d[\d\s-]{8,}\d")
_LEAD_MAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _lead_tier(score: int) -> str:
    if score >= 70:
        return "vip"
    if score >= 45:
        return "warm"
    return "cold"


def _build_sales_insight(messages: list, conv: Conversation) -> dict:
    user_texts = [str(m.content or "") for m in messages if (m.role or "") == "user"]
    joined = "\n".join(user_texts).lower()
    user_count = len(user_texts)
    score = 0
    reasons: list = []

    intent_terms = ("fiyat", "teklif", "kampanya", "taksit", "odeme", "ödeme", "demo", "randevu", "ne kadar", "satın al")
    objection_terms = ("pahali", "kararsiz", "düşün", "dusun", "guven", "yorum", "rakip", "emin degil", "emin değil")
    urgency_terms = ("bugun", "hemen", "acil", "simdi", "şimdi")
    if any(k in joined for k in intent_terms):
        score += 30
        reasons.append("Satin alma niyeti sinyali var")
    if any(k in joined for k in urgency_terms):
        score += 15
        reasons.append("Aciliyet ifadesi var")
    if _LEAD_PHONE_RE.search(joined) or _LEAD_MAIL_RE.search(joined) or conv.customer_phone:
        score += 20
        reasons.append("Iletisim bilgisi paylasilmis")
    if user_count >= 3:
        score += 10
        reasons.append("Yuksek etkilesim")
    if conv.last_message_at and conv.last_message_at >= datetime.utcnow() - timedelta(hours=2):
        score += 15
        reasons.append("Son mesaj cok yeni")
    if conv.notes:
        score += 5
    score = max(0, min(100, score))
    tier = _lead_tier(score)

    playbook: list = []
    if any(k in joined for k in objection_terms):
        playbook.append("Anliyorum, karar zor olabilir. Isterseniz size en uygun paket ve net fiyat araligini 1 dakikada cikarayim.")
    if "fiyat" in joined or "teklif" in joined:
        playbook.append("Butcenize gore 2 secenek hazirlayayim: hizli baslangic ve tam kapsam. Hangisiyle ilerleyelim?")
    if "demo" in joined:
        playbook.append("Demo hesabinizi hemen acabiliriz. Ad-soyad, e-posta ve web sitenizi paylasmaniz yeterli.")
    if not playbook:
        playbook.append("Ihtiyaciniza uygun en kisa yol haritasini cikarabilmem icin onceliginizi tek cumleyle yazar misiniz?")

    if tier == "vip":
        followup_minutes = 30
        followup_note = "VIP lead: 30 dk icinde geri donus"
    elif tier == "warm":
        followup_minutes = 120
        followup_note = "Sicak lead: 2 saat icinde geri donus"
    else:
        followup_minutes = 1440
        followup_note = "Lead takibi: 24 saat icinde geri donus"

    return {
        "score": score,
        "tier": tier,
        "reasons": reasons[:3],
        "playbook": playbook[:3],
        "followup_minutes": followup_minutes,
        "followup_note": followup_note,
    }


def _suggest_local_conf_threshold(
    base_threshold: int,
    total_attempts: int,
    low_conf_count: int,
    error_count: int,
    avg_conf: float | None,
) -> int:
    tuned = int(base_threshold)
    if total_attempts < 30:
        return tuned
    low_rate = low_conf_count / max(1, total_attempts)
    err_rate = error_count / max(1, total_attempts)
    if err_rate >= 0.25:
        tuned = min(85, tuned + 15)
    elif low_rate >= 0.55:
        tuned = min(82, tuned + 10)
    elif low_rate >= 0.40:
        tuned = min(78, tuned + 5)
    elif low_rate <= 0.12 and err_rate <= 0.05 and avg_conf is not None and avg_conf >= 78:
        tuned = max(45, tuned - 5)
    return int(tuned)


async def _compute_local_routing_metrics(db: AsyncSession, tenant_id: int, week_ago: datetime, base_threshold: int) -> dict:
    local_attempts_7 = 0
    local_accepted_7 = 0
    local_low_conf_7 = 0
    local_error_7 = 0
    local_conf_total = 0
    local_conf_count = 0
    local_rows = await db.execute(
        select(AuditLog.action, AuditLog.details)
        .where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.created_at >= week_ago,
            AuditLog.action.in_(("ai_local_accepted", "ai_local_low_confidence", "ai_local_error")),
        )
        .order_by(desc(AuditLog.id))
        .limit(400)
    )
    for action, details in local_rows.all():
        local_attempts_7 += 1
        if action == "ai_local_accepted":
            local_accepted_7 += 1
        elif action == "ai_local_low_confidence":
            local_low_conf_7 += 1
        elif action == "ai_local_error":
            local_error_7 += 1
        if details:
            try:
                payload = json.loads(details)
                conf = payload.get("confidence")
                if conf is not None:
                    local_conf_total += int(conf)
                    local_conf_count += 1
            except Exception:
                pass
    local_accept_rate_7 = round((local_accepted_7 / local_attempts_7) * 100, 1) if local_attempts_7 else 0.0
    local_avg_conf_7 = round(local_conf_total / local_conf_count, 1) if local_conf_count else 0.0
    local_suggested_threshold = _suggest_local_conf_threshold(
        base_threshold=base_threshold,
        total_attempts=local_attempts_7,
        low_conf_count=local_low_conf_7,
        error_count=local_error_7,
        avg_conf=(local_avg_conf_7 if local_conf_count else None),
    )
    return {
        "local_attempts_7": local_attempts_7,
        "local_accepted_7": local_accepted_7,
        "local_low_conf_7": local_low_conf_7,
        "local_error_7": local_error_7,
        "local_accept_rate_7": local_accept_rate_7,
        "local_avg_conf_7": local_avg_conf_7,
        "local_base_threshold": base_threshold,
        "local_suggested_threshold": local_suggested_threshold,
    }


SLA_RESPONSE_MINUTES = 10
SLA_AUTO_AGENT_NAME = "SLA Bot"
_last_sla_alert_at: dict = {}


async def _conversation_sla_state(db: AsyncSession, conv: Conversation, now: datetime) -> tuple:
    """Sohbette son user mesaji SLA disina tasmis mi?"""
    from sqlalchemy import func
    result = await db.execute(
        select(Message.role, Message.created_at)
        .where(Message.conversation_id == conv.id)
        .order_by(desc(Message.created_at))
        .limit(8)
    )
    rows = result.all()
    last_user_at = None
    last_assistant_at = None
    for role, created_at in rows:
        if role == "user" and last_user_at is None:
            last_user_at = created_at
        if role == "assistant" and last_assistant_at is None:
            last_assistant_at = created_at
    if not last_user_at:
        return False, None
    waiting_for_reply = (last_assistant_at is None) or (last_assistant_at < last_user_at)
    overdue = waiting_for_reply and (last_user_at <= now - timedelta(minutes=SLA_RESPONSE_MINUTES))
    return overdue, last_user_at


def _should_send_sla_alert(key: str, cooldown_minutes: int = 60) -> bool:
    now = datetime.utcnow()
    prev = _last_sla_alert_at.get(key)
    if prev and now - prev < timedelta(minutes=cooldown_minutes):
        return False
    _last_sla_alert_at[key] = now
    return True


async def _notify_sla_auto_takeover(tenant_id: int, conv: Conversation, last_user_at: datetime | None) -> None:
    from services.core.tenant import get_tenant_settings
    settings = await get_tenant_settings(tenant_id)
    email = (settings.get("health_alert_email") or "").strip()
    sms_webhook = (settings.get("health_alert_sms_webhook") or "").strip()
    if not email and not sms_webhook:
        return
    text = (
        f"SLA oto-devralma uyarisi\n"
        f"Tenant: {tenant_id}\n"
        f"Sohbet: {conv.id}\n"
        f"Musteri: {(conv.customer_name or conv.platform_user_id or 'Musteri')}\n"
        f"Son user mesaji: {(last_user_at.isoformat(timespec='seconds') + ' UTC') if last_user_at else '-'}\n"
        f"Esik: {SLA_RESPONSE_MINUTES} dk"
    )
    if email:
        try:
            app_cfg = get_settings()
            if app_cfg.smtp_host and app_cfg.smtp_user:
                msg = MIMEText(text, "plain", "utf-8")
                msg["Subject"] = "Emare Asistan - SLA Oto-Devralma"
                msg["From"] = formataddr(("Emare Asistan", app_cfg.smtp_from))
                msg["To"] = email
                with smtplib.SMTP(app_cfg.smtp_host, app_cfg.smtp_port) as server:
                    server.starttls()
                    server.login(app_cfg.smtp_user, app_cfg.smtp_password or "")
                    server.sendmail(app_cfg.smtp_from, email, msg.as_string())
        except Exception:
            pass
    if sms_webhook and (sms_webhook.startswith("http://") or sms_webhook.startswith("https://")):
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                await client.post(
                    sms_webhook,
                    json={"text": text, "tenant_id": tenant_id, "conversation_id": conv.id, "event": "sla_auto_takeover"},
                )
        except Exception:
            pass


def _norm_phone_for_match(value: str | None) -> str:
    s = str(value or "").replace("@s.whatsapp.net", "").replace("@c.us", "").replace("+", "").replace(" ", "")
    if s.startswith("0"):
        s = "90" + s[1:]
    return "".join(ch for ch in s if ch.isdigit())


async def _apply_sla_auto_takeover(db: AsyncSession, tid: int) -> int:
    """SLA asimi olan sohbetleri otomatik devral."""
    from sqlalchemy import func
    now = datetime.utcnow()
    result = await db.execute(
        select(Conversation)
        .where(Conversation.tenant_id == tid)
        .order_by(desc(func.coalesce(Conversation.last_message_at, Conversation.created_at)))
        .limit(120)
    )
    conversations = result.scalars().all()
    updated = 0
    for conv in conversations:
        if conv.agent_taken_over_at is not None:
            continue
        overdue, last_user_at = await _conversation_sla_state(db, conv, now)
        if not overdue:
            continue
        conv.agent_taken_over_at = now
        conv.agent_name = SLA_AUTO_AGENT_NAME
        old_notes = (conv.notes or "").strip()
        mark = f"[auto-sla] {SLA_RESPONSE_MINUTES} dk yanit SLO asildi; sohbet otomatik devralindi."
        conv.notes = f"{old_notes}\n{mark}".strip() if old_notes else mark
        updated += 1
        key = f"{tid}:{conv.id}:sla_auto"
        if _should_send_sla_alert(key):
            await _notify_sla_auto_takeover(tid, conv, last_user_at)
    if updated:
        await db.commit()
    return updated


async def _audit_from_request(
    request: Request,
    action: str,
    resource: str,
    resource_id: str,
    details: dict | None = None,
) -> None:
    from services.core.audit import log_audit
    await log_audit(
        action=action,
        resource=resource,
        resource_id=resource_id,
        details=json.dumps(details or {}, ensure_ascii=False)[:1500],
        tenant_id=get_tenant_id(request),
        user_id=request.session.get("user_id"),
        user_email=request.session.get("user_email"),
        ip_address=_request_client_ip(request),
    )


def _module_config_status(module_id: str, fields: list, mod_data: dict) -> str:
    """Modul ayarini etiketle: configured | missing"""
    if not isinstance(mod_data, dict):
        return "missing"
    clean_data = {k: v for k, v in mod_data.items() if not str(k).startswith("_")}
    if module_id == "cargo":
        company_ids = []
        for f in fields:
            key = f.get("key") or ""
            if key.endswith("_enabled"):
                company_ids.append(key[: -len("_enabled")])
        configured_count = 0
        for cid in company_ids:
            if str(clean_data.get(f"{cid}_api_url") or "").strip() or str(clean_data.get(f"{cid}_tracking_url") or "").strip():
                configured_count += 1
        return "configured" if configured_count > 0 else "missing"
    has_url = False
    for f in fields:
        if f.get("type") == "url" and str(clean_data.get(f.get("key") or "") or "").strip():
            has_url = True
            break
    if has_url:
        return "configured"
    has_any = any(str(v or "").strip() for v in clean_data.values())
    return "configured" if has_any else "missing"


async def _append_module_sync_log(tenant_id: int, module_id: str, entry: dict) -> None:
    """Sync sonucunu tenant.settings > module_apis > {module_id} > _sync_logs altinda sakla."""
    from services.core.crypto import encrypt_tenant_settings
    from services.core.cache import invalidate_tenant_cache

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if not tenant:
            return
        existing = {}
        raw = tenant.settings
        if isinstance(raw, str) and raw.strip():
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                existing = {}
        elif isinstance(raw, dict):
            existing = dict(raw)
        module_apis = dict(existing.get("module_apis") or {})
        module_data = dict(module_apis.get(module_id) or {})
        logs = module_data.get("_sync_logs")
        if not isinstance(logs, list):
            logs = []
        logs.insert(0, entry)
        module_data["_sync_logs"] = logs[:8]
        module_apis[module_id] = module_data
        existing["module_apis"] = module_apis
        tenant.settings = json.dumps(encrypt_tenant_settings(existing), ensure_ascii=False)
        await db.commit()
    await invalidate_tenant_cache(tenant_id)


def _branding_logo_ext(filename: str) -> str:
    """İzin verilen logo uzantısı (güvenli)."""
    ext = (Path(filename or "").suffix or ".png").lower()
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"):
        return ".png"
    return ext


async def save_branding_logo(
    file: UploadFile,
    request: Request,
    *,
    tenant_id: int | None = None,
    partner_id: int | None = None,
) -> str | None:
    """
    Yüklenen logo dosyasını uploads/branding/ altına kaydeder, dönen URL'yi döndürür.
    tenant_id veya partner_id verilmeli (tenant için tenant_id, partner için partner_id).
    """
    import uuid
    if not file or not file.filename:
        return None
    ct = (file.content_type or "").lower()
    if not ct.startswith("image/"):
        return None
    root = Path(__file__).resolve().parent.parent
    if tenant_id is not None:
        subdir = f"tenant_{tenant_id}"
    elif partner_id is not None:
        subdir = f"partner_{partner_id}"
    else:
        return None
    dest_dir = root / "uploads" / "branding" / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = _branding_logo_ext(file.filename)
    name = f"logo_{uuid.uuid4().hex[:12]}{ext}"
    dest = dest_dir / name
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB
        return None
    dest.write_bytes(content)
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/uploads/branding/{subdir}/{name}"
