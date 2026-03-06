"""
services/trendyol/sync.py — Trendyol Periyodik Senkronizasyon
================================================================
Cron veya Celery ile çağrılacak senkronizasyon fonksiyonları.
Soruları kontrol et, yanıtla, siparişleri çek.
"""

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import Tenant, Order
from models.database import AsyncSessionLocal
from services.trendyol import api
from services.trendyol.questions import process_question, categorize_question

logger = logging.getLogger("trendyol.sync")


# ════════════════════════════════════════════════════════
# TENANT AYARLARINI AL
# ════════════════════════════════════════════════════════

async def _get_trendyol_settings(db: AsyncSession, tenant_id: int) -> dict:
    """Tenant'ın Trendyol özel ayarlarını döner."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        return {}
    settings = tenant.settings or {}
    return settings.get("trendyol", {})


async def _save_trendyol_settings(db: AsyncSession, tenant_id: int, trendyol_settings: dict):
    """Tenant Trendyol ayarlarını günceller."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        return
    s = dict(tenant.settings or {})
    s["trendyol"] = trendyol_settings
    tenant.settings = s
    await db.commit()


# ════════════════════════════════════════════════════════
# SORU SENKRONİZASYONU
# ════════════════════════════════════════════════════════

async def sync_questions(tenant_id: int) -> dict:
    """
    Trendyol'daki bekleyen soruları çek, işle, yanıtla.
    Döner: {total, answered, pending, errors}
    """
    async with AsyncSessionLocal() as db:
        settings = await _get_trendyol_settings(db, tenant_id)
        questions = await api.get_questions(tenant_id)

        if not questions:
            return {"total": 0, "answered": 0, "pending": 0, "errors": 0}

        # Daha önce yanıtlanan soruları takip et
        answered_ids = set(settings.get("answered_ids", []))
        question_log = settings.get("question_log", [])
        pending_list = settings.get("pending_questions", [])

        stats = {"total": 0, "answered": 0, "pending": 0, "errors": 0}

        for q in questions:
            qid = q.get("id")
            qtext = (q.get("text") or "").strip()
            product_info = q.get("productName", "")

            if not qid or qid in answered_ids or not qtext:
                continue

            stats["total"] += 1
            logger.info("Trendyol soru [T%s][Q%s]: %s", tenant_id, qid, qtext[:80])

            try:
                result = await process_question(
                    tenant_id, qid, qtext, product_info, settings)

                # Log'a ekle
                question_log.append({
                    "question_id": qid,
                    "question": qtext,
                    "answer": result["answer"],
                    "method": result["method"],
                    "confidence": result["confidence"],
                    "category": result["category"],
                    "product_info": product_info,
                    "timestamp": result["timestamp"],
                    "answered": result["answered"],
                })

                if result["answered"]:
                    stats["answered"] += 1
                    answered_ids.add(qid)
                elif result["method"] in ("pending", "keyword_pending", "fuzzy_pending"):
                    stats["pending"] += 1
                    pending_list.append({
                        "question_id": qid,
                        "question": qtext,
                        "suggested_answer": result["answer"],
                        "confidence": result["confidence"],
                        "product_info": product_info,
                        "category": result["category"],
                        "timestamp": result["timestamp"],
                        "status": "pending",
                    })
                else:
                    stats["pending"] += 1
                    pending_list.append({
                        "question_id": qid,
                        "question": qtext,
                        "suggested_answer": "",
                        "confidence": 0.0,
                        "product_info": product_info,
                        "category": result["category"],
                        "timestamp": result["timestamp"],
                        "status": "no_match",
                    })
            except Exception as e:
                stats["errors"] += 1
                logger.error("Trendyol soru işleme hatası [Q%s]: %s", qid, e)

        # Son 500 log ve 200 answered_id tut
        settings["question_log"] = question_log[-500:]
        settings["answered_ids"] = list(answered_ids)[-200:]
        settings["pending_questions"] = [p for p in pending_list if p.get("status") == "pending"]
        settings["last_sync"] = datetime.now().isoformat()
        settings["last_sync_stats"] = stats

        await _save_trendyol_settings(db, tenant_id, settings)

    return stats


# ════════════════════════════════════════════════════════
# SİPARİŞ SENKRONİZASYONU
# ════════════════════════════════════════════════════════

TRENDYOL_STATUS_MAP = {
    "Created": "pending",
    "Picking": "processing",
    "Invoiced": "processing",
    "Shipped": "shipped",
    "Delivered": "delivered",
    "Cancelled": "cancelled",
    "UnDelivered": "cancelled",
    "Returned": "cancelled",
}


async def sync_orders(tenant_id: int, days: int = 7) -> dict:
    """
    Trendyol siparişlerini çek, yerel Order tablosuna kaydet/güncelle.
    Döner: {total, created, updated, errors}
    """
    async with AsyncSessionLocal() as db:
        trendyol_orders = await api.get_orders(tenant_id, days=days)

        if not trendyol_orders:
            return {"total": 0, "created": 0, "updated": 0, "errors": 0}

        stats = {"total": len(trendyol_orders), "created": 0, "updated": 0, "errors": 0}

        for torder in trendyol_orders:
            try:
                order_number = str(torder.get("orderNumber", ""))
                if not order_number:
                    continue

                # Var mı kontrol
                existing = await db.execute(
                    select(Order).where(
                        Order.tenant_id == tenant_id,
                        Order.order_number == f"TR-{order_number}",
                    )
                )
                db_order = existing.scalar_one_or_none()

                # Sipariş kalemleri
                lines = torder.get("lines", [])
                items = []
                total = 0.0
                for line in lines:
                    item = {
                        "name": line.get("productName", ""),
                        "barcode": line.get("barcode", ""),
                        "quantity": line.get("quantity", 1),
                        "price": line.get("amount", 0),
                        "sku": line.get("merchantSku", ""),
                    }
                    items.append(item)
                    total += float(item["price"]) * int(item["quantity"])

                # Müşteri bilgileri
                ship = torder.get("shipmentAddress", {})
                customer_name = f"{ship.get('firstName', '')} {ship.get('lastName', '')}".strip()
                customer_phone = ship.get("phone1", "") or ship.get("phone2", "")
                customer_address = f"{ship.get('address1', '')} {ship.get('address2', '')} {ship.get('district', '')} {ship.get('city', '')}".strip()

                # Trendyol durum → yerel durum
                trendyol_status = torder.get("status", "")
                local_status = TRENDYOL_STATUS_MAP.get(trendyol_status, "pending")

                # Kargo
                cargo_tracking = ""
                cargo_company = ""
                packages = torder.get("cargoTrackingNumber")
                if packages:
                    cargo_tracking = str(packages)
                cargo_company = torder.get("cargoProviderName", "")

                if db_order:
                    # Güncelle
                    db_order.status = local_status
                    db_order.items = json.dumps(items, ensure_ascii=False)
                    db_order.total_amount = total
                    if cargo_tracking:
                        db_order.cargo_tracking_no = cargo_tracking
                    if cargo_company:
                        db_order.cargo_company = cargo_company
                    db_order.notes = f"Trendyol durum: {trendyol_status}"
                    stats["updated"] += 1
                else:
                    # Yeni sipariş oluştur
                    new_order = Order(
                        tenant_id=tenant_id,
                        order_number=f"TR-{order_number}",
                        customer_name=customer_name,
                        customer_phone=customer_phone,
                        customer_address=customer_address,
                        payment_option="Trendyol",
                        items=json.dumps(items, ensure_ascii=False),
                        total_amount=total,
                        status=local_status,
                        cargo_tracking_no=cargo_tracking,
                        cargo_company=cargo_company,
                        platform="trendyol",
                        notes=f"Trendyol sipariş: {order_number} | Durum: {trendyol_status}",
                    )
                    db.add(new_order)
                    stats["created"] += 1

            except Exception as e:
                stats["errors"] += 1
                logger.error("Trendyol sipariş sync hatası: %s", e)

        await db.commit()

    return stats


# ════════════════════════════════════════════════════════
# YORUM SENKRONİZASYONU
# ════════════════════════════════════════════════════════

async def sync_reviews(tenant_id: int) -> dict:
    """Trendyol yorumlarını çek ve tenant ayarlarına kaydet."""
    async with AsyncSessionLocal() as db:
        all_reviews = await api.fetch_all_reviews(tenant_id, max_pages=10)

        # Ürün bazında grupla
        grouped: dict[str, list] = {}
        for r in all_reviews:
            prod = (r.get("productName") or "Bilinmeyen").strip()
            entry = {
                "comment": (r.get("comment") or "").strip(),
                "rate": r.get("rate", 0),
                "user": f"{r.get('customerFirstName', '')} {r.get('customerLastName', '')}".strip(),
                "date": "",
            }
            ts = r.get("lastModifiedDate") or r.get("createdDate")
            if ts:
                try:
                    entry["date"] = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
                except Exception:
                    pass
            if entry["comment"]:
                grouped.setdefault(prod, []).append(entry)

        # Kaydet
        settings = await _get_trendyol_settings(db, tenant_id)
        settings["reviews_cache"] = grouped
        settings["reviews_last_sync"] = datetime.now().isoformat()
        settings["reviews_total"] = sum(len(v) for v in grouped.values())
        settings["reviews_products"] = len(grouped)
        await _save_trendyol_settings(db, tenant_id, settings)

    total = sum(len(v) for v in grouped.values())
    return {"total_reviews": total, "products": len(grouped)}


# ════════════════════════════════════════════════════════
# TÜM SYNC (CRON İÇİN)
# ════════════════════════════════════════════════════════

async def sync_all_tenants() -> dict:
    """Trendyol modülü aktif tüm tenant'ları senkronize eder."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.is_active == True))
        tenants = result.scalars().all()

    results = {}
    for tenant in tenants:
        modules = (tenant.settings or {}).get("enabled_modules", [])
        if "trendyol" not in modules:
            continue
        try:
            q_stats = await sync_questions(tenant.id)
            o_stats = await sync_orders(tenant.id)
            results[tenant.id] = {"questions": q_stats, "orders": o_stats}
            logger.info("Trendyol sync [T%s]: Q=%s O=%s", tenant.id, q_stats, o_stats)
        except Exception as e:
            logger.error("Trendyol sync hatası [T%s]: %s", tenant.id, e)
            results[tenant.id] = {"error": str(e)}

    return results
