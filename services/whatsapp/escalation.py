"""
Smart Escalation - Müşteri memnuniyetsizliği tespiti.
Son mesajlarda "hayır", "yanlış", "anlamadım" vb. geçerse AI'a temsilci devri önerisi eklenir.
"""
FRUSTRATION_KEYWORDS = [
    "hayır", "yanlış", "anlamadım", "anlamıyorum", "değil", "olmadı", "yok",
    "olmadı", "çalışmıyor", "işe yaramadı", "yardım", "temsilci", "insan",
    "kızgınım", "sinir", "çok kötü", "berbat", "rezalet",
]


def detect_frustration(history: list[dict], threshold: int = 3) -> bool:
    """
    Sohbet geçmişinde hayal kırıklığı tespit et.
    history: [{"role": "user"|"assistant", "content": "..."}, ...]
    threshold: Kaç mesajda keyword geçerse tetiklenir (varsayılan 3)
    """
    user_messages = [h.get("content", "") for h in history if h.get("role") == "user"]
    count = 0
    for msg in user_messages[-10:]:  # Son 10 kullanıcı mesajı
        msg_lower = (msg or "").lower()
        if any(kw in msg_lower for kw in FRUSTRATION_KEYWORDS):
            count += 1
        if count >= threshold:
            return True
    return False


def get_escalation_context() -> str:
    """AI'a eklenecek escalation bağlamı"""
    return (
        "\n\nÖNEMLİ: Müşteri son mesajlarda memnuniyetsizlik ifadesi kullandı (hayır, yanlış, anlamadım vb.). "
        "Nazikçe özür dileyin ve 'Temsilcimizle görüşmek ister misiniz?' veya 'Sizi bir uzmanımıza bağlayayım mı?' diye sorun. "
        "Müşteri onaylarsa temsilci devri yapılacak."
    )
