"""
Ödeme linki servisi - Iyzico Link API ile sipariş için ödeme linki oluşturur.
Kredi kartı seçildiğinde WhatsApp'tan link gönderilir.
"""
import asyncio
import base64
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 1x1 placeholder PNG (transparent) - Iyzico encodedImageFile zorunlu
_PLACEHOLDER_IMAGE_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


def _create_iyzico_link_sync(
    api_key: str,
    secret_key: str,
    base_url: str,
    order_number: str,
    product_name: str,
    description: str,
    price: float,
    currency: str = "TRY",
) -> Optional[str]:
    """Iyzico Link oluştur - sync (iyzipay sync API)"""
    try:
        import iyzipay

        options = {
            "api_key": api_key,
            "secret_key": secret_key,
            "base_url": base_url,
        }
        request = {
            "locale": "tr",
            "conversationId": order_number,
            "name": product_name[:100],
            "description": description[:255],
            "price": f"{price:.2f}",
            "currencyCode": currency,
            "encodedImageFile": _PLACEHOLDER_IMAGE_B64,
            "addressIgnorable": True,
            "installmentRequested": False,
        }
        report = iyzipay.IyziLinkProduct().create(request, options)
        data = json.loads(report.read().decode("utf-8"))
        if data.get("status") == "success" and data.get("data", {}).get("url"):
            return data["data"]["url"]
    except Exception as e:
        logger.warning("Iyzico Link oluşturma hatası: %s", e)
    return None


async def create_payment_link(
    tenant_settings: dict,
    order_number: str,
    items: list[dict],
    total: float,
) -> Optional[str]:
    """
    Sipariş için Iyzico ödeme linki oluştur.
    tenant_settings: get_tenant_settings() veya module_apis["payment"]
    Returns: ödeme URL veya None
    """
    module_apis = tenant_settings.get("module_apis") or {}
    payment_cfg = module_apis.get("payment") or {}
    api_key = (payment_cfg.get("iyzico_api_key") or "").strip()
    secret_key = (payment_cfg.get("iyzico_secret_key") or "").strip()
    if not api_key or not secret_key:
        return None
    if api_key == "••••••••••••" or secret_key == "••••••••••••":
        return None  # Maskelenmiş, gerçek key yok

    sandbox = (payment_cfg.get("iyzico_sandbox") or "").strip().lower() in ("1", "true", "evet")
    base_url = "sandbox-api.iyzipay.com" if sandbox else "api.iyzipay.com"

    product_name = "Sipariş " + order_number
    desc_parts = [f"{i.get('name', 'Ürün')} x{i.get('quantity', 1)}" for i in items[:5]]
    description = ", ".join(desc_parts) or "Sipariş"

    loop = asyncio.get_event_loop()
    url = await loop.run_in_executor(
        None,
        lambda: _create_iyzico_link_sync(
            api_key=api_key,
            secret_key=secret_key,
            base_url=base_url,
            order_number=order_number,
            product_name=product_name,
            description=description,
            price=total,
        ),
    )
    return url
