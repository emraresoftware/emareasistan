"""
Randevu servisi - Müsait slot hesaplama, randevu oluşturma.
tenant_settings: appointment_work_hours (09:00-18:00), appointment_slot_minutes (30), appointment_work_days (1,2,3,4,5)
"""
from datetime import datetime, timedelta
import re
from typing import Optional

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models import Appointment, Message
from services.core.tenant import get_module_api_settings


def _parse_work_hours(work_hours: str) -> tuple[int, int]:
    """09:00-18:00 -> (9, 18)"""
    if not work_hours or "-" not in work_hours:
        return 9, 18
    try:
        start, end = work_hours.strip().split("-")
        h1 = int(start.strip().split(":")[0])
        h2 = int(end.strip().split(":")[0])
        return min(h1, h2), max(h1, h2)
    except Exception:
        return 9, 18


def _parse_work_days(work_days: str) -> set[int]:
    """1,2,3,4,5 -> {1,2,3,4,5} (1=Pazartesi, 7=Pazar)"""
    if not work_days or not work_days.strip():
        return {1, 2, 3, 4, 5}
    try:
        return set(int(x.strip()) for x in work_days.split(",") if x.strip())
    except Exception:
        return {1, 2, 3, 4, 5}


async def get_available_slots(
    db: AsyncSession,
    tenant_id: int,
    from_date: datetime,
    days_ahead: int = 7,
    work_hours: str = "09:00-18:00",
    slot_minutes: int = 30,
    work_days: str = "1,2,3,4,5",
) -> list[datetime]:
    """
    Müsait randevu slotları döndür.
    Mevcut randevuları çıkarır.
    """
    start_h, end_h = _parse_work_hours(work_hours)
    days = _parse_work_days(work_days)
    slots = []
    base = datetime(from_date.year, from_date.month, from_date.day, 0, 0, 0)

    for day_offset in range(days_ahead):
        d = base + timedelta(days=day_offset)
        iso_weekday = d.isoweekday()
        if iso_weekday not in days:
            continue
        day_start = datetime(d.year, d.month, d.day, start_h, 0, 0)
        day_end = datetime(d.year, d.month, d.day, end_h, 0, 0)
        slot = day_start
        while slot < day_end:
            if slot >= from_date:
                slots.append(slot)
            slot += timedelta(minutes=slot_minutes)
            if len(slots) >= 30:
                break
        if len(slots) >= 30:
            break

    # DB'deki meşgul randevuları çıkar
    if slots:
        start_slot = min(slots)
        end_slot = max(slots) + timedelta(minutes=slot_minutes)
        result = await db.execute(
            select(Appointment.scheduled_at)
            .where(
                and_(
                    Appointment.tenant_id == tenant_id,
                    Appointment.status.in_(["pending", "confirmed"]),
                    Appointment.scheduled_at >= start_slot,
                    Appointment.scheduled_at < end_slot,
                )
            )
        )
        busy = {r[0].replace(second=0, microsecond=0) for r in result.scalars().all()}
        slots = [s for s in slots if s.replace(second=0, microsecond=0) not in busy]

    return slots[:20]  # En fazla 20 slot


async def create_appointment(
    db: AsyncSession,
    tenant_id: int,
    scheduled_at: datetime,
    customer_name: str,
    customer_phone: str,
    conversation_id: Optional[int] = None,
    contact_id: Optional[int] = None,
    service_type: Optional[str] = None,
    note: Optional[str] = None,
) -> Appointment:
    """Randevu oluştur"""
    apt = Appointment(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        contact_id=contact_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        scheduled_at=scheduled_at,
        service_type=service_type,
        note=note,
        status="pending",
    )
    db.add(apt)
    await db.commit()
    await db.refresh(apt)

    # Baslangic entegrasyonu: opsiyonel Google Calendar webhook
    try:
        cfg = await get_module_api_settings(tenant_id, "appointments")
        enabled = str(cfg.get("calendar_sync_enabled") or "").strip().lower() in ("1", "true", "on", "yes")
        webhook_url = (cfg.get("google_calendar_webhook_url") or "").strip()
        if enabled and webhook_url and (webhook_url.startswith("http://") or webhook_url.startswith("https://")):
            payload = {
                "event": "appointment_created",
                "tenant_id": tenant_id,
                "appointment_id": apt.id,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "scheduled_at": scheduled_at.isoformat(),
                "service_type": service_type or "",
                "note": note or "",
            }
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                await client.post(webhook_url, json=payload)
    except Exception:
        # Randevu kaydini etkilemesin
        pass
    return apt


_DATE_RE = re.compile(r"\b([0-3]?\d)[./-]([01]?\d)[./-](20\d{2})\b")
_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")


def _note_contains_misparsed_pattern(text: str, scheduled_at: datetime) -> bool:
    """
    Eski bug'da 14.02.2026 gibi bir tarih, 14:02 saatine donusebiliyordu.
    Bu patterni tarih metni uzerinden yakalar.
    """
    for m in _DATE_RE.finditer(text or ""):
        day = int(m.group(1))
        month = int(m.group(2))
        if day == scheduled_at.hour and month == scheduled_at.minute:
            # Saatin "gun.ay"dan gelmis olmasi cok guclu bir sinyal.
            # Net bir HH:MM ayni degilse bu kayit buyuk ihtimalle eski parse bug'idir.
            return True
    return False


def _extract_times(text: str) -> set[tuple[int, int]]:
    out: set[tuple[int, int]] = set()
    for m in _TIME_RE.finditer(text or ""):
        out.add((int(m.group(1)), int(m.group(2))))
    return out


async def cleanup_misparsed_date_appointments(
    db: AsyncSession,
    tenant_id: int,
    appointment_id: int | None = None,
) -> list[int]:
    """
    Eski tarih->saat parse bug'i nedeniyle olusan hatali randevulari iptal eder.
    Kural:
    - pending/confirmed ve conversation baglantili olacak
    - Ilgili sohbette tarih (dd.mm.yyyy) geciyor olacak
    - Sohbette net HH:MM saat gecmiyor olacak
    - Randevu saati, gecen tarihin gun.ay desenine uyuyor olacak (14:02 gibi)
    """
    query = select(Appointment).where(
        Appointment.tenant_id == tenant_id,
        Appointment.status.in_(["pending", "confirmed"]),
        Appointment.conversation_id.isnot(None),
    )
    if appointment_id is not None:
        query = query.where(Appointment.id == appointment_id)
    result = await db.execute(query)
    appointments = result.scalars().all()

    cleaned_ids: list[int] = []
    for apt in appointments:
        sibling_res = await db.execute(
            select(Appointment).where(
                Appointment.conversation_id == apt.conversation_id,
                Appointment.tenant_id == apt.tenant_id,
                Appointment.status.in_(["pending", "confirmed"]),
                Appointment.id != apt.id,
            )
        )
        siblings = sibling_res.scalars().all()

        msg_rows = await db.execute(
            select(Message.content).where(Message.conversation_id == apt.conversation_id)
        )
        texts = [str(t or "") for t in msg_rows.scalars().all()]
        if not texts:
            continue
        joined = "\n".join(texts)
        looks_misparsed = _note_contains_misparsed_pattern(joined, apt.scheduled_at)
        if not looks_misparsed:
            continue

        # Ayni sohbette farkli saatte baska aktif randevu varsa bu kayit neredeyse kesin hatalidir.
        if any(
            (s.scheduled_at.hour, s.scheduled_at.minute) != (apt.scheduled_at.hour, apt.scheduled_at.minute)
            for s in siblings
        ):
            apt.status = "cancelled"
            old_note = (apt.note or "").strip()
            cleanup_note = "[auto-cleanup] Tarih metni (gg.aa.yyyy) eski bug nedeniyle saat gibi algilanmis."
            apt.note = f"{old_note}\n{cleanup_note}".strip() if old_note else cleanup_note
            cleaned_ids.append(int(apt.id))
            continue

        seen_times = _extract_times(joined)
        if (apt.scheduled_at.hour, apt.scheduled_at.minute) in seen_times:
            # Sohbette bu saat net olarak geciyorsa randevu muhtemelen dogrudur.
            continue
        apt.status = "cancelled"
        old_note = (apt.note or "").strip()
        cleanup_note = "[auto-cleanup] Tarih metni (gg.aa.yyyy) eski bug nedeniyle saat gibi algilanmis."
        apt.note = f"{old_note}\n{cleanup_note}".strip() if old_note else cleanup_note
        cleaned_ids.append(int(apt.id))
    if cleaned_ids:
        await db.commit()
    return cleaned_ids
