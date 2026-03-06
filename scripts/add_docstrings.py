#!/usr/bin/env python3
"""
Route fonksiyonlarına otomatik docstring ekler.
Fonksiyon adı ve dekoratöründen anlam çıkarır.
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Fonksiyon adından Türkçe docstring üreten sözlük
VERB_MAP = {
    "list": "listeler",
    "new": "yeni oluşturma formu",
    "edit": "düzenleme formu",
    "save": "kaydeder",
    "delete": "siler",
    "create": "oluşturur",
    "upload": "dosya yükler",
    "detail": "detay sayfası",
    "export": "dışa aktarır",
    "import": "içe aktarır",
    "clear": "temizler",
    "complete": "tamamlanmış olarak işaretler",
    "cancel": "iptal eder",
    "status": "durum sorgular",
    "settings": "ayarlar sayfası",
    "save": "kaydeder",
    "toggle": "açar/kapatır",
    "page": "sayfasını gösterir",
    "proxy": "proxy eder",
    "sync": "senkronize eder",
    "preview": "önizleme gösterir",
    "test": "test eder",
    "submit": "gönderir",
    "update": "günceller",
}

NOUN_MAP = {
    "album": "Albüm",
    "albums": "Albümler",
    "video": "Video",
    "videos": "Videolar",
    "product": "Ürün",
    "products": "Ürünler",
    "order": "Sipariş",
    "orders": "Siparişler",
    "conversation": "Sohbet",
    "conversations": "Sohbetler",
    "contact": "Kişi",
    "contacts": "Kişiler",
    "reminder": "Hatırlatıcı",
    "reminders": "Hatırlatıcılar",
    "rule": "Kural",
    "rules": "Kurallar",
    "user": "Kullanıcı",
    "users": "Kullanıcılar",
    "whatsapp": "WhatsApp bağlantısı",
    "appointment": "Randevu",
    "appointments": "Randevular",
    "training": "Eğitim verisi",
    "workflow": "İş akışı",
    "workflows": "İş akışları",
    "quick_replies": "Hızlı yanıtlar",
    "cargo": "Kargo",
    "feedback": "Geri bildirim",
    "export_template": "Dışa aktarım şablonu",
    "export_templates": "Dışa aktarım şablonları",
    "partner": "Partner",
    "settings": "Ayarlar",
    "dashboard": "Dashboard",
    "analytics": "Analitik",
    "agent": "Temsilci",
    "staff": "Personel",
    "leave": "İzin",
    "leaves": "İzinler",
    "invoice": "Fatura",
    "invoices": "Faturalar",
    "purchase_order": "Satın alma siparişi",
    "purchase_orders": "Satın alma siparişleri",
    "chat_audit": "Sohbet denetimi",
    "chat_audits": "Sohbet denetimleri",
    "process_config": "Süreç yapılandırması",
    "telegram": "Telegram",
    "instagram": "Instagram",
    "web_chat": "Web sohbet",
    "branding": "Marka",
    "tenant": "Tenant",
    "tenants": "Tenantlar",
    "login": "Giriş",
    "logout": "Çıkış",
    "register": "Kayıt",
}

def generate_docstring(func_name: str, method: str = "", path: str = "") -> str:
    """Fonksiyon adından Türkçe docstring üretir."""
    parts = func_name.split("_")
    
    # prefix'leri atla: admin_, api_, _redirect_ vs.
    skip = {"admin", "api", "redirect", "cron"}
    cleaned = [p for p in parts if p.lower() not in skip and p]
    if not cleaned:
        cleaned = parts
    
    # Son kelime genellikle verb
    verb_word = cleaned[-1] if cleaned else ""
    noun_words = cleaned[:-1] if len(cleaned) > 1 else cleaned
    
    # Noun'u bul
    noun_key = "_".join(noun_words).lower()
    noun = NOUN_MAP.get(noun_key, "")
    if not noun and len(noun_words) > 0:
        noun = NOUN_MAP.get(noun_words[0].lower(), noun_key.replace("_", " ").title())
    
    # Verb'u bul
    verb = VERB_MAP.get(verb_word.lower(), "")
    
    if verb and noun:
        doc = f"{noun} {verb}."
    elif verb:
        doc = f"{func_name.replace('_', ' ').title()} - {verb}."
    elif noun:
        doc = f"{noun} endpoint'i."
    else:
        doc = f"{func_name.replace('_', ' ').title()} işlemi."
    
    # Method + path bilgisi varsa ekle
    if method and path:
        doc += f" [{method} {path}]"
    
    return doc


def add_docstrings_to_file(filepath: Path, dry_run: bool = False) -> int:
    """Dosyadaki docstring'siz route fonksiyonlarına docstring ekler."""
    text = filepath.read_text()
    lines = text.split("\n")
    new_lines = []
    added = 0
    
    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        
        # @router.get/post/put/delete dekoratörü
        route_match = re.match(r'\s*@\w+\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)', line)
        if route_match:
            method = route_match.group(1).upper()
            path = route_match.group(2)
            
            # Fonksiyon tanımını bul (sonraki birkaç satır)
            j = i + 1
            func_line_idx = None
            while j < len(lines) and j < i + 10:
                if re.match(r'\s*(async\s+)?def\s+\w+', lines[j]):
                    func_line_idx = j
                    break
                new_lines.append(lines[j])
                j += 1
            
            if func_line_idx is not None:
                func_line = lines[func_line_idx]
                func_match = re.match(r'(\s*)(async\s+)?def\s+(\w+)\s*\(', func_line)
                
                if func_match:
                    indent = func_match.group(1)
                    func_name = func_match.group(3)
                    
                    # Fonksiyon gövdesinin başlangıcını bul (parametrelerin bittiği yer)
                    # ): ile biten satırı bul
                    new_lines.append(func_line)
                    k = func_line_idx + 1
                    
                    # Parametrelerin sonunu bul
                    paren_count = func_line.count("(") - func_line.count(")")
                    while paren_count > 0 and k < len(lines):
                        new_lines.append(lines[k])
                        paren_count += lines[k].count("(") - lines[k].count(")")
                        k += 1
                    
                    # Şimdi k, fonksiyon gövdesinin ilk satırı
                    if k < len(lines):
                        next_line = lines[k].strip()
                        # Zaten docstring var mı?
                        if next_line.startswith('"""') or next_line.startswith("'''"):
                            # Zaten var, dokunma
                            i = k
                            continue
                        else:
                            # Docstring ekle
                            body_indent = indent + "    "
                            docstring = generate_docstring(func_name, method, path)
                            new_lines.append(f'{body_indent}"""{docstring}"""')
                            added += 1
                            i = k
                            continue
                    
                    i = k
                    continue
            
            i = j
            continue
        
        i += 1
    
    if added > 0 and not dry_run:
        filepath.write_text("\n".join(new_lines))
    
    return added


def main():
    dry_run = "--dry-run" in sys.argv
    
    targets = [
        ROOT / "admin" / "routes.py",
        ROOT / "admin" / "routes_agent.py",
        ROOT / "admin" / "routes_dashboard.py",
        ROOT / "admin" / "routes_settings.py",
        ROOT / "admin" / "routes_orders.py",
        ROOT / "admin" / "routes_auth.py",
        ROOT / "admin" / "routes_rules_workflows.py",
        ROOT / "admin" / "routes_partner_super.py",
        ROOT / "admin" / "partner.py",
        ROOT / "integrations" / "whatsapp_qr.py",
        ROOT / "integrations" / "whatsapp_webhook.py",
        ROOT / "integrations" / "chat_handler.py",
        ROOT / "integrations" / "bridge_api.py",
        ROOT / "integrations" / "telegram_bot.py",
        ROOT / "integrations" / "web_chat_api.py",
        ROOT / "integrations" / "support_chat_api.py",
        ROOT / "integrations" / "cron_api.py",
        ROOT / "services" / "ai_assistant.py",
        ROOT / "services" / "order_service.py",
        ROOT / "services" / "product_service.py",
        ROOT / "services" / "tenant_service.py",
        ROOT / "services" / "cargo_service.py",
        ROOT / "services" / "agent_send.py",
        ROOT / "services" / "email_service.py",
        ROOT / "services" / "website_analyzer.py",
    ]
    
    total = 0
    mode_str = "DRY-RUN" if dry_run else "YAZILIYOR"
    print(f"🔥 Kıvılcım Docstring Ekleme ({mode_str})\n")
    
    for f in targets:
        if f.exists():
            count = add_docstrings_to_file(f, dry_run)
            if count:
                print(f"  📝 {f.relative_to(ROOT)}: {count} docstring eklendi")
            total += count
    
    print(f"\n  Toplam: {total} docstring {'eklenecek' if dry_run else 'eklendi'}")


if __name__ == "__main__":
    main()
