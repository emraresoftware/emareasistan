"""
services/trendyol/api.py — Trendyol Seller API İstemcisi
=========================================================
Tenant bazında API kimlik bilgilerini kullanarak Trendyol Seller API'sine
istek atar: Soru-Cevap, Sipariş, İade/Talep, Ürün Yorumları.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from services.core.tenant import get_module_api_settings

logger = logging.getLogger("trendyol.api")

# ────────────────────────────────────────────────────────
# Yardımcı — Tenant'a özel API istemcisi döner
# ────────────────────────────────────────────────────────

async def _get_client_config(tenant_id: int) -> dict | None:
    """Tenant ayarlarından Trendyol API bilgilerini döner."""
    cfg = await get_module_api_settings(tenant_id, "trendyol")
    if not cfg:
        return None
    seller_id = cfg.get("trendyol_seller_id", "").strip()
    api_key = cfg.get("trendyol_api_key", "").strip()
    api_secret = cfg.get("trendyol_api_secret", "").strip()
    supplier_id = cfg.get("trendyol_supplier_id", "").strip() or seller_id
    if not (seller_id and api_key and api_secret):
        return None
    return {
        "seller_id": seller_id,
        "supplier_id": supplier_id,
        "api_key": api_key,
        "api_secret": api_secret,
        "auth": (api_key, api_secret),
        "headers": {
            "User-Agent": f"{supplier_id} - SelfIntegration",
            "Content-Type": "application/json",
        },
    }


async def _api_get(cfg: dict, url: str) -> dict | None:
    """Ortak GET isteği."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                url,
                headers=cfg["headers"],
                auth=cfg["auth"],
            )
            if r.status_code == 200:
                return r.json()
            logger.warning("Trendyol API GET %s: %s", r.status_code, url)
    except Exception as e:
        logger.error("Trendyol API bağlantı hatası: %s", e)
    return None


async def _api_post(cfg: dict, url: str, payload: dict) -> tuple[bool, str]:
    """Ortak POST isteği. -> (başarılı, mesaj)"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                url,
                headers=cfg["headers"],
                auth=cfg["auth"],
                json=payload,
            )
            if r.status_code == 200:
                return True, "OK"
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        logger.error("Trendyol API POST hatası: %s", e)
        return False, str(e)


# ════════════════════════════════════════════════════════
# SORU-CEVAP (Q&A)
# ════════════════════════════════════════════════════════

async def get_questions(tenant_id: int, status: str = "WAITING_FOR_ANSWER") -> list[dict]:
    """Trendyol'daki bekleyen müşteri sorularını çeker."""
    cfg = await _get_client_config(tenant_id)
    if not cfg:
        return []
    url = (f"https://apigw.trendyol.com/integration/qna/sellers/"
           f"{cfg['supplier_id']}/questions/filter?status={status}")
    data = await _api_get(cfg, url)
    if data and "content" in data:
        return data["content"]
    return []


async def answer_question(tenant_id: int, question_id: int, answer_text: str) -> tuple[bool, str]:
    """Trendyol sorusuna yanıt gönderir."""
    cfg = await _get_client_config(tenant_id)
    if not cfg:
        return False, "API yapılandırılmamış"
    url = (f"https://apigw.trendyol.com/integration/qna/sellers/"
           f"{cfg['supplier_id']}/questions/{question_id}/answers")
    return await _api_post(cfg, url, {"text": answer_text})


# ════════════════════════════════════════════════════════
# SİPARİŞLER
# ════════════════════════════════════════════════════════

async def get_orders(tenant_id: int, days: int = 7) -> list[dict]:
    """Son N günün Trendyol siparişlerini çeker."""
    cfg = await _get_client_config(tenant_id)
    if not cfg:
        return []
    end_ts = int(datetime.now().timestamp() * 1000)
    start_ts = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    url = (f"https://apigw.trendyol.com/integration/order/sellers/"
           f"{cfg['supplier_id']}/orders?startDate={start_ts}&endDate={end_ts}")
    data = await _api_get(cfg, url)
    return data.get("content", []) if data else []


async def get_order_detail(tenant_id: int, order_number: str) -> dict | None:
    """Tek sipariş detayını çeker."""
    cfg = await _get_client_config(tenant_id)
    if not cfg:
        return None
    url = (f"https://apigw.trendyol.com/integration/order/sellers/"
           f"{cfg['supplier_id']}/orders?orderNumber={order_number}")
    data = await _api_get(cfg, url)
    content = data.get("content", []) if data else []
    return content[0] if content else None


# ════════════════════════════════════════════════════════
# İADE / TALEPLERİ
# ════════════════════════════════════════════════════════

async def get_claims(tenant_id: int, days: int = 30) -> list[dict]:
    """Son N günün iade/taleplerini çeker."""
    cfg = await _get_client_config(tenant_id)
    if not cfg:
        return []
    end_ts = int(datetime.now().timestamp() * 1000)
    start_ts = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    url = (f"https://apigw.trendyol.com/integration/order/sellers/"
           f"{cfg['supplier_id']}/claims?startDate={start_ts}&endDate={end_ts}")
    data = await _api_get(cfg, url)
    return data.get("content", []) if data else []


# ════════════════════════════════════════════════════════
# ÜRÜN YORUMLARI
# ════════════════════════════════════════════════════════

async def fetch_reviews(tenant_id: int, page: int = 0, size: int = 100) -> list[dict]:
    """Ürün yorumlarını sayfa sayfa çeker."""
    cfg = await _get_client_config(tenant_id)
    if not cfg:
        return []
    url = (f"https://apigw.trendyol.com/integration/product/sellers/"
           f"{cfg['supplier_id']}/products/reviews"
           f"?page={page}&size={size}&status=APPROVED")
    data = await _api_get(cfg, url)
    return data.get("content", []) if data else []


async def fetch_all_reviews(tenant_id: int, max_pages: int = 10) -> list[dict]:
    """Tüm sayfalardaki yorumları çeker."""
    all_reviews: list[dict] = []
    for pg in range(max_pages):
        batch = await fetch_reviews(tenant_id, page=pg, size=100)
        if not batch:
            break
        all_reviews.extend(batch)
        if len(batch) < 100:
            break
    return all_reviews


# ════════════════════════════════════════════════════════
# ÜRÜNLER
# ════════════════════════════════════════════════════════

async def get_products(tenant_id: int, page: int = 0, size: int = 50) -> dict:
    """Trendyol'daki ürünleri listeler."""
    cfg = await _get_client_config(tenant_id)
    if not cfg:
        return {"content": [], "totalElements": 0}
    url = (f"https://apigw.trendyol.com/integration/product/sellers/"
           f"{cfg['supplier_id']}/products?page={page}&size={size}")
    data = await _api_get(cfg, url)
    return data or {"content": [], "totalElements": 0}


async def update_product_stock(tenant_id: int, barcode: str, quantity: int) -> tuple[bool, str]:
    """Ürün stok günceller."""
    cfg = await _get_client_config(tenant_id)
    if not cfg:
        return False, "API yapılandırılmamış"
    url = (f"https://apigw.trendyol.com/integration/inventory/sellers/"
           f"{cfg['supplier_id']}/products/stock-updates")
    payload = {"items": [{"barcode": barcode, "quantity": quantity}]}
    return await _api_post(cfg, url, payload)


async def update_product_price(tenant_id: int, barcode: str,
                                list_price: float, sale_price: float) -> tuple[bool, str]:
    """Ürün fiyat günceller."""
    cfg = await _get_client_config(tenant_id)
    if not cfg:
        return False, "API yapılandırılmamış"
    url = (f"https://apigw.trendyol.com/integration/inventory/sellers/"
           f"{cfg['supplier_id']}/products/price-updates")
    payload = {"items": [{"barcode": barcode, "listPrice": list_price, "salePrice": sale_price}]}
    return await _api_post(cfg, url, payload)


# ════════════════════════════════════════════════════════
# DURUM KONTROLÜ
# ════════════════════════════════════════════════════════

async def check_connection(tenant_id: int) -> tuple[bool, str]:
    """Trendyol API bağlantısını kontrol eder."""
    cfg = await _get_client_config(tenant_id)
    if not cfg:
        return False, "API bilgileri eksik veya yapılandırılmamış"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            url = (f"https://apigw.trendyol.com/integration/product/sellers/"
                   f"{cfg['supplier_id']}/products?page=0&size=1")
            r = await client.get(url, headers=cfg["headers"], auth=cfg["auth"])
            if r.status_code == 200:
                return True, "Bağlantı başarılı"
            return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)
