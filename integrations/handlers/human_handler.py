"""HumanHandler - Temsilci devralma durumunda yanıt"""


class HumanHandler:
    """Temsilci sohbeti devraldıysa AI yanıt vermez"""

    @staticmethod
    def should_hand_over(conv) -> bool:
        """Temsilci devralmış mı?"""
        return bool(conv and conv.agent_taken_over_at)

    @staticmethod
    def get_response() -> dict:
        """Temsilci modunda döndürülecek yanıt"""
        return {
            "text": "Mesajınız temsilcimize iletildi. En kısa sürede dönüş yapacağız.",
            "agent_mode": True,
        }
