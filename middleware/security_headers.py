"""
Güvenlik header'ları middleware.
Tüm yanıtlara temel güvenlik başlıkları ekler.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Tüm HTTP yanıtlarına güvenlik başlıkları ekleyen middleware."""

    async def dispatch(self, request: Request, call_next):
        """Yanıta X-Frame-Options, CSP, HSTS gibi güvenlik başlıkları ekler."""
        response = await call_next(request)

        # Clickjacking koruması
        response.headers["X-Frame-Options"] = "SAMEORIGIN"

        # XSS koruması
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer politikası
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy — gereksiz tarayıcı özelliklerini kapat
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # HSTS — sadece HTTPS'de aktif (proxy arkasındaysa header'dan anla)
        if request.headers.get("x-forwarded-proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response
