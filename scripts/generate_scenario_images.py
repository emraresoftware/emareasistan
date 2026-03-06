#!/usr/bin/env python3
"""
Emare Asistan — Senaryo Kart Görselleri Üretici
WhatsApp / Web sohbetlerde "örnek senaryo" istendiğinde gönderilecek kart görselleri.
Her kart: renkli başlık, sektör etiketi, simüle sohbet baloncukları, CTA.
"""
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ── Ayarlar ──
W, H = 800, 1000
RADIUS = 24
CARD_BG = "#FFFFFF"
BUBBLE_USER = "#DCF8C6"
BUBBLE_BOT = "#E8EAF6"
TEXT_DARK = "#1a1a2e"
TEXT_MID = "#475569"
TEXT_LIGHT = "#94a3b8"

OUT_DIR = Path(__file__).resolve().parent.parent / "static" / "scenarios"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def get_font(size: int, bold: bool = False):
    """Sisteme uygun font bul."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-Bold.ttf" if bold else "/usr/share/fonts/truetype/ubuntu/Ubuntu-Regular.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                continue
    return ImageFont.load_default()


def draw_rounded_rect(draw, xy, fill, radius=16):
    """Yuvarlatılmış dikdörtgen çiz."""
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def draw_bubble(draw, x, y, text, color, font, max_w=420, is_right=False):
    """Sohbet baloncuğu çiz. is_right=True: kullanıcı (sağda)."""
    # Metni satırlara sar
    words = text.split()
    lines = []
    current = ""
    for w in words:
        test = f"{current} {w}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_w - 24:
            if current:
                lines.append(current)
            current = w
        else:
            current = test
    if current:
        lines.append(current)

    line_h = font.size + 6
    bub_h = len(lines) * line_h + 20
    bub_w = max_w

    bx = x if not is_right else x - bub_w
    draw_rounded_rect(draw, (bx, y, bx + bub_w, y + bub_h), fill=color, radius=14)

    ty = y + 10
    for line in lines:
        draw.text((bx + 12, ty), line, fill=TEXT_DARK, font=font)
        ty += line_h

    return bub_h + 8


def create_scenario_card(
    filename: str,
    header_color: str,
    emoji: str,
    sector: str,
    title: str,
    chat_messages: list[tuple[str, str]],  # list of (role, text) — "user" or "bot"
    footer_text: str = "",
):
    """Tek bir senaryo kart görseli oluştur."""
    img = Image.new("RGB", (W, H), "#f1f5f9")
    draw = ImageDraw.Draw(img)

    font_title = get_font(28, bold=True)
    font_sector = get_font(16, bold=True)
    font_chat = get_font(18)
    font_footer = get_font(14)
    font_emoji = get_font(40)
    font_label = get_font(13, bold=True)

    # ── Kart arka planı ──
    card_x, card_y = 30, 30
    card_w, card_h = W - 60, H - 60
    draw_rounded_rect(draw, (card_x, card_y, card_x + card_w, card_y + card_h), fill=CARD_BG, radius=RADIUS)

    # ── Başlık bandı ──
    header_h = 120
    draw_rounded_rect(
        draw,
        (card_x, card_y, card_x + card_w, card_y + header_h + 10),
        fill=header_color,
        radius=RADIUS,
    )
    # Alt köşeleri kapatmak için düz dikdörtgen
    draw.rectangle((card_x, card_y + header_h - 10, card_x + card_w, card_y + header_h + 10), fill=header_color)

    # Emoji
    draw.text((card_x + 30, card_y + 18), emoji, fill="#FFFFFF", font=font_emoji)

    # Sektör etiketi
    draw_rounded_rect(
        draw,
        (card_x + card_w - 160, card_y + 16, card_x + card_w - 20, card_y + 42),
        fill="#FFFFFF33",
        radius=10,
    )
    draw.text((card_x + card_w - 150, card_y + 19), sector, fill="#FFFFFF", font=font_sector)

    # Başlık
    draw.text((card_x + 30, card_y + 68), title, fill="#FFFFFF", font=font_title)

    # ── Sohbet baloncukları ──
    cy = card_y + header_h + 30

    for role, text in chat_messages:
        is_user = role == "user"
        label = "Müşteri" if is_user else "🤖 Emare Asistan"
        label_font = font_label
        label_color = "#16a34a" if is_user else "#4f46e5"

        if is_user:
            draw.text((card_x + card_w - 120, cy), label, fill=label_color, font=label_font)
        else:
            draw.text((card_x + 50, cy), label, fill=label_color, font=label_font)
        cy += 20

        bubble_color = BUBBLE_USER if is_user else BUBBLE_BOT
        if is_user:
            bh = draw_bubble(draw, card_x + card_w - 50, cy, text, bubble_color, font_chat, max_w=380, is_right=True)
        else:
            bh = draw_bubble(draw, card_x + 50, cy, text, bubble_color, font_chat, max_w=420)
        cy += bh + 4

    # ── Alt bilgi ──
    if footer_text:
        fy = card_y + card_h - 50
        draw.text((card_x + 40, fy), footer_text, fill=TEXT_LIGHT, font=font_footer)

    # ── Emare Asistan markası ──
    draw_rounded_rect(
        draw,
        (card_x + card_w - 220, card_y + card_h - 50, card_x + card_w - 20, card_y + card_h - 24),
        fill="#f1f5f9",
        radius=8,
    )
    draw.text(
        (card_x + card_w - 210, card_y + card_h - 47),
        "⚡ Emare Asistan",
        fill="#6366f1",
        font=font_sector,
    )

    # Kaydet
    out_path = OUT_DIR / filename
    img.save(str(out_path), "PNG", quality=92)
    print(f"  ✅ {out_path}")
    return str(out_path)


# ═══════════════════════════════════════════════════════════════
# SENARYOLAR
# ═══════════════════════════════════════════════════════════════

SCENARIOS = [
    {
        "filename": "musteri_karsilama.png",
        "header_color": "#6366f1",
        "emoji": "👋",
        "sector": "E-Ticaret",
        "title": "Müşteri Karşılama",
        "chat": [
            ("user", "Merhaba, ürünleriniz hakkında bilgi almak istiyorum"),
            ("bot", "Merhaba! Hoş geldiniz 😊 Size nasıl yardımcı olabilirim? Ürün kataloğumuzu incelemenize yardımcı olabilirim."),
            ("user", "Koltuk kılıfı bakıyorum"),
            ("bot", "Tabii! Araç modelinizi paylaşır mısınız? Size uygun ürünleri hemen göstereyim."),
        ],
        "footer": "7/24 otomatik karşılama • Sektöre özel selamlama",
    },
    {
        "filename": "siparis_takip.png",
        "header_color": "#0ea5e9",
        "emoji": "📦",
        "sector": "E-Ticaret",
        "title": "Sipariş & Kargo Takibi",
        "chat": [
            ("user", "Siparişim nerede?"),
            ("bot", "Sipariş numaranızı veya telefon numaranızı paylaşır mısınız? Hemen kontrol edeyim."),
            ("user", "1042"),
            ("bot", "Siparişiniz kargoya verildi 🚚 Takip No: TR8294712. Tahmini teslim: Yarın 14:00-18:00 arası."),
        ],
        "footer": "Otomatik kargo sorgulama • Anlık durum bildirimi",
    },
    {
        "filename": "randevu_planlama.png",
        "header_color": "#8b5cf6",
        "emoji": "📅",
        "sector": "Sağlık / Hizmet",
        "title": "Randevu Planlama",
        "chat": [
            ("user", "Randevu almak istiyorum"),
            ("bot", "Memnuniyetle! Hangi gün ve saat aralığı sizin için uygun?"),
            ("user", "Yarın 14:00 olabilir mi?"),
            ("bot", "Yarın 14:00 için randevunuz oluşturuldu ✅ Ad Soyad ve telefon numaranızla teyit edelim mi?"),
        ],
        "footer": "Otomatik takvim entegrasyonu • SMS/WhatsApp teyit",
    },
    {
        "filename": "trendyol_soru_cevap.png",
        "header_color": "#f97316",
        "emoji": "🛒",
        "sector": "Pazar Yeri",
        "title": "Trendyol Soru-Cevap",
        "chat": [
            ("user", "Bu ürün XL bedene uygun mu?"),
            ("bot", "Evet, ürünümüz XL beden için uygundur. Boy: 180-190cm, Kilo: 90-100kg aralığına göre tasarlanmıştır."),
            ("user", "Kumaş kalitesi nasıl?"),
            ("bot", "Premium polyester kumaş kullanılmaktadır. Su geçirmez ve leke tutmaz özelliğe sahiptir."),
        ],
        "footer": "Trendyol AI otomatik yanıt • Ürün bilgisi eşleştirme",
    },
    {
        "filename": "temsilci_devir.png",
        "header_color": "#10b981",
        "emoji": "🔄",
        "sector": "Genel",
        "title": "Temsilci Devralma",
        "chat": [
            ("user", "Bir sorunum var, yetkiliye bağlar mısınız?"),
            ("bot", "Tabii, sizi hemen bir temsilcimize yönlendiriyorum. Kısa süre içinde dönüş yapılacaktır."),
            ("bot", "Temsilci Ayşe sohbeti devraldı. Nasıl yardımcı olabilirim?"),
        ],
        "footer": "Tek tıkla temsilci devri • Sohbet notları aktarımı",
    },
    {
        "filename": "coklu_kanal.png",
        "header_color": "#ec4899",
        "emoji": "📱",
        "sector": "Tüm Sektörler",
        "title": "Çoklu Kanal Yönetimi",
        "chat": [
            ("user", "Instagram'dan yazdım, web sitedeki ürünü soruyorum"),
            ("bot", "Tüm kanallardan gelen mesajlarınız tek panelde! Hangi ürünle ilgileniyorsunuz?"),
            ("user", "Siyah deri çanta"),
            ("bot", "İşte siyah deri çanta modellerimiz. WhatsApp, Instagram veya web üzerinden sipariş verebilirsiniz."),
        ],
        "footer": "WhatsApp + Instagram + Web + Telegram → Tek panel",
    },
]


def main():
    print("🎨 Senaryo kartları oluşturuluyor...\n")
    for sc in SCENARIOS:
        create_scenario_card(
            filename=sc["filename"],
            header_color=sc["header_color"],
            emoji=sc["emoji"],
            sector=sc["sector"],
            title=sc["title"],
            chat_messages=sc["chat"],
            footer_text=sc.get("footer", ""),
        )
    print(f"\n✅ {len(SCENARIOS)} senaryo kartı oluşturuldu: {OUT_DIR}")


if __name__ == "__main__":
    main()
