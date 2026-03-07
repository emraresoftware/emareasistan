"""ProductHandler - Ürün arama, vision, albüm, kural eşleşmesi"""
from __future__ import annotations
import json
from sqlalchemy import select

from models import ImageAlbum
from services.product.vehicles import extract_vehicle_from_message


class ProductHandler:
    """Ürün bağlamı ve resim listesi oluşturma"""

    def __init__(self, db, rule_engine):
        self.db = db
        self.rule_engine = rule_engine

    async def build_product_context(
        self,
        products_svc,
        message_text: str,
        msg_normalized: str,
        intent: str,
        image_base64: str | None,
        image_mimetype: str | None,
    ) -> tuple[str, list[dict]]:
        """
        Ürün araması + vision. Returns (product_context, searched_products).
        """
        product_context = ""
        searched_products = []
        product_keywords = [
            "ürün", "koltuk", "paspas", "elit", "ekonom", "fiyat", "kılıf", "7d",
            "bagaj", "yastık", "zemin", "döşeme", "resim", "foto", "deri", "jant",
            "organizer", "kolçak", "yaka", "araba", "araç", "model",
            "karşılaştır", "karşılaştırma", "fark", "hangisi",
        ]

        if image_base64:
            # Plaka/ruhsat OCR - mesajda ilgili kelime varsa önce OCR dene
            ocr_keywords = ["plaka", "ruhsat", "şasi", "sasi", "vin", "araç belgesi"]
            if any(k in msg_normalized for k in ocr_keywords):
                from services.ai.ocr import extract_plate_or_vin
                ocr_result = await extract_plate_or_vin(image_base64)
                if ocr_result.get("plate") or ocr_result.get("vin") or ocr_result.get("raw_text"):
                    lines = []
                    if ocr_result.get("plate"):
                        lines.append(f"Plaka: {ocr_result['plate']}")
                    if ocr_result.get("vin"):
                        lines.append(f"Şasi/VIN: {ocr_result['vin']}")
                    if ocr_result.get("raw_text") and not (ocr_result.get("plate") or ocr_result.get("vin")):
                        lines.append(f"Okunan metin: {ocr_result['raw_text'][:200]}...")
                    if lines:
                        product_context = "Müşteri plaka/ruhsat resmi gönderdi. OCR sonucu:\n" + "\n".join(lines)
                        return product_context, []
            from services.ai.vision import match_image_to_product
            all_products = await products_svc.get_all_for_vision()
            if all_products:
                matched = await match_image_to_product(
                    image_base64,
                    all_products,
                    image_mimetype or "image/jpeg",
                )
                if matched:
                    searched_products = [matched]
                    product_context = products_svc.get_product_context(searched_products)
                    return product_context, searched_products
            product_context = "Müşteri ürün resmi gönderdi. Katalogda benzer ürün bulunamadı. Nazikçe bilgilendir."
            return product_context, []

        if "product" not in intent and not any(k in msg_normalized for k in product_keywords):
            return product_context, searched_products

        search_query = msg_normalized or (message_text or "")
        vehicle = extract_vehicle_from_message(search_query)
        searched_products = await products_svc.search(query=search_query, vehicle=vehicle or "")
        if not searched_products:
            searched_products = await products_svc.search(query="")

        comparison_words = ["karşılaştır", "karşılaştırma", "fark", "hangisi", "aralarındaki"]
        if any(w in msg_normalized for w in comparison_words) and len(searched_products) < 2:
            diverse = await products_svc.get_diverse_products(max_count=6, vehicle=vehicle or "")
            if diverse:
                searched_products = diverse

        product_context = products_svc.get_product_context(searched_products)
        return product_context, searched_products

    async def get_album_images(self, vehicle: str, tenant_id: int) -> dict | None:
        """Araç modeline göre albüm getir"""
        if not vehicle or not vehicle.strip():
            return None
        vehicle_lower = vehicle.strip().lower()
        result = await self.db.execute(
            select(ImageAlbum)
            .where(
                ImageAlbum.tenant_id == tenant_id,
                ImageAlbum.is_active == True,
            )
            .order_by(ImageAlbum.priority.desc(), ImageAlbum.id)
        )
        albums = result.scalars().all()
        best_album = None
        best_score = (999, 0)
        for album in albums:
            models_str = album.vehicle_models or ""
            values = [v.strip().lower() for v in models_str.split(",") if v.strip()]
            matched = any(
                v == vehicle_lower or v in vehicle_lower or vehicle_lower in v
                for v in values
            )
            if not matched:
                continue
            try:
                urls = json.loads(album.image_urls or "[]")
            except json.JSONDecodeError:
                continue
            images = []
            for url in urls[:10]:
                if isinstance(url, str) and url.startswith("http"):
                    images.append({"url": url, "name": album.name or "", "price": None})
            if images:
                score = (len(values), -(album.priority or 0))
                if score < best_score:
                    best_album = {"images": images, "custom_message": album.custom_message or None}
                    best_score = score
        return best_album

    async def get_product_images_for_response(
        self,
        products_svc,
        msg_normalized: str,
        message_text: str,
        searched_products: list[dict],
        response: dict,
        tenant_id: int,
    ) -> list[dict]:
        """
        Yanıta eklenecek ürün resimleri: albüm, diverse, veya arama sonuçları.
        RuleEngine sonuçları ChatHandler'da ayrıca birleştirilir.
        """
        product_images = []
        explicit_image_words = ["resim", "foto", "görsel", "resimleri", "fotolar", "görseller"]
        all_products_words = ["tüm ürünler", "hepsini", "hepsini göster", "tüm resimler", "tümünü", "hepsinin"]
        inquiry_words = ["var mı", "varmı", "bakayım", "göster", "ne var", "olsun", "istiyorum", "göreyim", "bakalım"]

        user_wants_images = any(w in msg_normalized for w in explicit_image_words)
        explicit_send_request = any(w in msg_normalized for w in ["resim yolla", "resim gönder", "yolla", "gönder", "paylaş"]) and user_wants_images
        wants_all_products = any(w in msg_normalized for w in all_products_words)
        vehicle = extract_vehicle_from_message(message_text)
        word_count = len((message_text or "").strip().split())
        vehicle_inquiry = vehicle and (word_count <= 4 or any(iw in msg_normalized for iw in inquiry_words))

        if not (user_wants_images or vehicle_inquiry):
            return product_images

        use_diverse = wants_all_products or explicit_send_request
        if use_diverse:
            diverse = await products_svc.get_diverse_products(max_count=10, vehicle=vehicle or "")
            for p in diverse:
                if p.get("image_url"):
                    product_images.append({
                        "url": p["image_url"],
                        "name": p.get("name", ""),
                        "price": p.get("price"),
                    })
            if product_images:
                response["text"] = "İşte ürünlerimiz:"
            return product_images

        album_result = await self.get_album_images(vehicle, tenant_id) if vehicle else None
        if album_result:
            product_images = album_result["images"]
            if album_result.get("custom_message"):
                response["text"] = (album_result["custom_message"] + "\n\n" + (response.get("text") or "")).strip()
            return product_images

        if searched_products:
            if response.get("suggested_products"):
                for pid in response["suggested_products"][:6]:
                    idx = pid - 1 if isinstance(pid, int) else 0
                    if 0 <= idx < len(searched_products):
                        p = searched_products[idx]
                        if p.get("image_url"):
                            product_images.append({
                                "url": p["image_url"],
                                "name": p.get("name", ""),
                                "price": p.get("price"),
                            })
            if not product_images:
                for p in searched_products[:8]:
                    if p.get("image_url"):
                        product_images.append({
                            "url": p["image_url"],
                            "name": p.get("name", ""),
                            "price": p.get("price"),
                        })
            if product_images and explicit_send_request:
                response["text"] = "İşte ürünlerimiz:"

        return product_images
