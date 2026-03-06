"""
Rate limiting middleware - IP bazlı, in-memory.
Webhook ve login gibi hassas endpoint'leri korur.
"""
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


# IP -> [(timestamp, path_prefix), ...] - son 60 sn
_request_log: dict[str, list[tuple[float, str]]] = defaultdict(list)
_CLEANUP_INTERVAL = 60.0
_LAST_CLEANUP = time.time()

# Limitler: (path_prefix, max_per_minute)
_LIMITS = [
    ("/webhook/whatsapp", 120),   # WhatsApp webhook - yüksek trafik
    ("/admin/login", 10),          # Login brute-force koruması
    ("/admin/register", 5),        # Kayıt spam
    ("/api/whatsapp/process", 30), # QR process
]
# Genel limit: /admin veya /api için dakikada 100
_GLOBAL_LIMIT = 100


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _cleanup():
    global _LAST_CLEANUP
    now = time.time()
    if now - _LAST_CLEANUP < _CLEANUP_INTERVAL:
        return
    _LAST_CLEANUP = now
    cutoff = now - 60.0
    for ip in list(_request_log.keys()):
        _request_log[ip] = [(t, p) for t, p in _request_log[ip] if t > cutoff]
        if not _request_log[ip]:
            del _request_log[ip]


def _check_limit(ip: str, path: str) -> bool:
    _cleanup()
    now = time.time()
    cutoff = now - 60.0
    records = [(t, p) for t, p in _request_log[ip] if t > cutoff]
    _request_log[ip] = records

    for prefix, max_per_min in _LIMITS:
        if path.startswith(prefix):
            count = sum(1 for _, p in records if p.startswith(prefix))
            if count >= max_per_min:
                return False

    admin_or_api = path.startswith("/admin") or path.startswith("/api")
    if admin_or_api:
        if len(records) >= _GLOBAL_LIMIT:
            return False

    records.append((now, path))
    _request_log[ip] = records[-200:]  # Son 200 kayıt
    return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    """IP tabanlı rate limiting middleware. Endpoint'e göre farklı limitler uygular."""

    async def dispatch(self, request: Request, call_next):
        """Gelen isteği rate limit kontrolünden geçirir, aşımda 429 döner."""
        path = request.scope.get("path", "")
        if path in ("/", "/health", "/status", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)
        if path.startswith("/static") or path.startswith("/uploads"):
            return await call_next(request)

        ip = _get_client_ip(request)
        if not _check_limit(ip, path):
            return JSONResponse(
                status_code=429,
                content={"detail": "Çok fazla istek. Lütfen biraz bekleyin."},
            )
        return await call_next(request)
