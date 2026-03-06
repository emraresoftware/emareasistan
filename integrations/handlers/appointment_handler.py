"""AppointmentHandler - Randevu bağlamı, müsait slot bilgisi ve randevu oluşturma"""

from datetime import datetime

from services.appointment.service import get_available_slots, create_appointment as create_appointment_svc
from services.core.time_utils import now_turkey


class AppointmentHandler:
    """Randevu niyeti için AI bağlamı oluştur"""

    def __init__(self, db):
        self.db = db

    async def build_context(
        self,
        tenant_id: int,
        tenant_settings: dict,
        message_text: str,
        intent: str,
        msg_normalized: str,
    ) -> str:
        """
        Randevu niyetinde müsait slotları AI'a ver.
        """
        if intent != "appointment":
            return ""

        from datetime import datetime

        work_hours = tenant_settings.get("appointment_work_hours") or "09:00-18:00"
        slot_minutes = int(tenant_settings.get("appointment_slot_minutes") or 30)
        work_days = tenant_settings.get("appointment_work_days") or "1,2,3,4,5"

        slots = await get_available_slots(
            self.db,
            tenant_id,
            now_turkey(),
            days_ahead=7,
            work_hours=work_hours,
            slot_minutes=slot_minutes,
            work_days=work_days,
        )

        if not slots:
            return (
                "Müşteri randevu istiyor. Önümüzdeki 7 günde müsait slot yok. "
                "Nazikçe 'Şu an müsait slotumuz yok, lütfen telefonla arayın' de."
            )

        # İlk 8 slotu formatla (gün adı, saat)
        day_names = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        lines = []
        for s in slots[:8]:
            day_name = day_names[s.weekday()]
            time_str = s.strftime("%H:%M")
            lines.append(f"- {day_name} {s.strftime('%d.%m')} saat {time_str}")

        return (
            "Müşteri randevu hakkında bir şey sordu veya randevu almak istiyor."
            " Önümüzdeki müsait slotlar:\n"
            + "\n".join(lines)
            + "\n\n"
            "RANDEVU KURALI - ADIM ADIM:\n"
            "1. Eğer müşteri sadece randevu olup olmadığını soruyorsa veya belirsizse: "
            "suggest_replies ile 2-3 seçenek sun (örn: Randevu almak istiyorum / Önce fiyat öğrenmek istiyorum / Başka sorum var).\n"
            "2. Eğer müşteri açıkça randevu almak istediğini söylemişse: yukarıdaki slotlardan 2-3 öneri sun (hepsini listeleme).\n"
            "3. Müşteri slotu onayladığında: ad soyad ve telefon numarasını sor. "
            "İkisi de varsa create_appointment ile kaydet.\n"
            "4. KESINLIKLE ISRARCI OLMA. Müşteri 'düşüneceğim' veya farklı bir şey sorduysa randevuya zorıama.\n"
            "5. Her yanıtta slotları tekrar listeleme — yalnızca sorulduğunda veya müşteri hazır olduğunda göster."
        )

    async def process_create_appointment(
        self,
        response: dict,
        conv,
        tenant_id: int,
    ) -> dict:
        """
        AI create_appointment döndürdüyse randevu oluştur.
        response'u günceller, aynı response döndürür.
        """
        if not response.get("create_appointment"):
            return response

        data = response["create_appointment"]
        scheduled_str = (data.get("scheduled_at") or "").strip()
        name = (data.get("customer_name") or "").strip()
        phone = (data.get("customer_phone") or "").strip()

        if not (scheduled_str and name and phone):
            response["text"] = (response.get("text", "").split("```json")[0].strip() or "")
            return response

        try:
            scheduled_at = None
            for fmt in ("%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M:%S"):
                try:
                    scheduled_at = datetime.strptime(scheduled_str, fmt)
                    break
                except ValueError:
                    continue
            if not scheduled_at:
                response["text"] = (response.get("text", "").split("```json")[0].strip() or "")
                return response
        except Exception:
            response["text"] = (response.get("text", "").split("```json")[0].strip() or "")
            return response

        apt = await create_appointment_svc(
            self.db,
            tenant_id=tenant_id,
            scheduled_at=scheduled_at,
            customer_name=name,
            customer_phone=phone,
            conversation_id=conv.id,
        )

        day_names = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        day_name = day_names[scheduled_at.weekday()]
        summary = (
            f"✅ *Randevunuz Alındı*\n\n"
            f"📅 {day_name} {scheduled_at.strftime('%d.%m.%Y')} saat {scheduled_at.strftime('%H:%M')}\n"
            f"👤 {name}\n"
            f"📞 {phone}\n\n"
            f"Randevunuz kaydedildi. Görüşmek üzere!"
        )

        response["text"] = (response.get("text", "").split("```json")[0].strip() or "") + f"\n\n{summary}"
        return response
