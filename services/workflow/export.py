"""
Veri aktarım servisi - ExportTemplate ile formatlı veri oluşturma ve webhook gönderme.
"""
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Kaynak bazlı varsayılan alanlar (asistan alan adları)
SOURCE_FIELDS = {
    "orders": [
        "order_number", "customer_name", "customer_phone", "customer_address",
        "payment_option", "items", "total_amount", "status", "platform",
        "cargo_tracking_no", "cargo_company", "created_at",
    ],
    "contacts": [
        "name", "phone", "email", "notes", "created_at",
    ],
    "reminders": [
        "customer_name", "customer_phone", "due_at", "note", "status", "created_at",
    ],
}


def _order_to_dict(order) -> dict:
    """Order model → dict (items JSON parse)"""
    items_raw = order.items
    if isinstance(items_raw, str):
        try:
            items = json.loads(items_raw) if items_raw else []
        except json.JSONDecodeError:
            items = []
    else:
        items = items_raw or []
    return {
        "order_number": order.order_number,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "customer_address": order.customer_address,
        "payment_option": order.payment_option,
        "items": items,
        "total_amount": float(order.total_amount or 0),
        "status": order.status,
        "platform": order.platform,
        "cargo_tracking_no": order.cargo_tracking_no,
        "cargo_company": order.cargo_company,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


def _contact_to_dict(contact) -> dict:
    """Contact model → dict"""
    return {
        "name": contact.name,
        "phone": contact.phone,
        "email": getattr(contact, "email", None) or "",
        "notes": contact.notes or "",
        "created_at": contact.created_at.isoformat() if contact.created_at else None,
    }


def _reminder_to_dict(reminder) -> dict:
    """Reminder model → dict"""
    return {
        "customer_name": reminder.customer_name,
        "customer_phone": reminder.customer_phone,
        "due_at": reminder.due_at.isoformat() if reminder.due_at else None,
        "note": reminder.note or "",
        "status": reminder.status or "",
        "created_at": reminder.created_at.isoformat() if reminder.created_at else None,
    }


def apply_field_mapping(raw: dict, field_mapping: dict | None, source: str) -> dict:
    """
    Ham veriyi field_mapping'e göre dönüştür.
    field_mapping: {"order.customer_name": "musteri_adi", "customer_name": "musteri_adi"}
    raw key'leri "order.xxx", "orders.xxx" veya "xxx" formatında kabul eder.
    """
    if not field_mapping or not isinstance(field_mapping, dict):
        return raw

    out = {}
    for src_key, dst_key in field_mapping.items():
        if not dst_key:
            continue
        # src_key: "order.customer_name", "orders.customer_name" veya "customer_name"
        lookup = src_key.split(".")[-1] if "." in src_key else src_key
        if lookup in raw:
            out[dst_key] = raw[lookup]
    return out if out else raw


def build_payload(obj, source: str, field_mapping: dict | None) -> dict:
    """Model objesini template'e göre payload'a çevir."""
    if source == "orders":
        raw = _order_to_dict(obj)
    elif source == "contacts":
        raw = _contact_to_dict(obj)
    elif source == "reminders":
        raw = _reminder_to_dict(obj)
    else:
        raw = {}

    if field_mapping:
        return apply_field_mapping(raw, field_mapping, source)
    return raw


async def send_webhook(url: str, payload: dict, timeout: float = 10.0) -> bool:
    """Webhook URL'e JSON POST gönder."""
    if not url or not url.strip().startswith(("http://", "https://")):
        return False
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url.strip(), json=payload)
            if r.status_code >= 400:
                logger.warning("Export webhook %s returned %s", url[:50], r.status_code)
                return False
            return True
    except Exception as e:
        logger.exception("Export webhook failed: %s", e)
        return False
