"""
Pipeline - Sanitizer → Intent → Router → Formatter
Mesaj işleme zinciri. ChatHandler bu pipeline'ı kullanır.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .sanitizer import MessageSanitizer
from .router import MessageRouter, RouteInfo
from .formatter import ResponseFormatter
from services.workflow.metrics import record_pipeline_event


@dataclass
class PipelineInput:
    """Pipeline girişi"""
    raw_message: str
    image_base64: Optional[str] = None


@dataclass
class PipelineOutput:
    """Pipeline çıkışı - bağlam toplama ve yanıt için"""
    sanitized_message: str
    route_info: RouteInfo
    display_message: str  # Kullanıcıya kaydedilecek metin (resim varsa "[Resim]" vb.)


class MessagePipeline:
    """
    Mesaj işleme pipeline'ı:
    1. Sanitizer: Temizle, normalleştir
    2. Intent: Niyet tespit (IntentDetector)
    3. Router: Modül öncelikleri
    4. Formatter: Yanıt formatlama (response üretildikten sonra)
    """

    def __init__(self):
        self.sanitizer = MessageSanitizer()
        self.router = MessageRouter()
        self.formatter = ResponseFormatter()

    def process_input(self, raw_message: str, image_base64: Optional[str] = None, tenant_id: int = 1) -> PipelineOutput:
        """
        Gelen mesajı işle, PipelineOutput döndür.
        ChatHandler bu çıktıyı kullanarak bağlam toplar ve AI çağrısı yapar.
        """
        started = datetime.utcnow()
        try:
            sanitized = self.sanitizer.sanitize(raw_message or "")
            route_info = self.router.route(sanitized or raw_message or "")
            display = (raw_message or "").strip() or ("[Resim gönderildi]" if image_base64 else "")
            latency_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
            record_pipeline_event(
                tenant_id,
                ok=True,
                latency_ms=latency_ms,
                intent=route_info.intent,
                primary_module=route_info.primary_module,
            )
            return PipelineOutput(
                sanitized_message=sanitized or (raw_message or "").lower(),
                route_info=route_info,
                display_message=display,
            )
        except Exception:
            latency_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
            record_pipeline_event(
                tenant_id,
                ok=False,
                latency_ms=latency_ms,
                intent="unknown",
                primary_module="ai",
            )
            raise

    def format_response(self, response: dict, platform: str = "whatsapp") -> dict:
        """Yanıtı platform formatına uyarla"""
        return self.formatter.format(response, platform)
