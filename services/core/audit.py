"""Audit log servisi - admin aksiyonlarını kaydet"""
from typing import Optional

from models.database import AsyncSessionLocal
from models.audit_log import AuditLog


async def log_audit(
    action: str,
    resource: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[str] = None,
    tenant_id: Optional[int] = None,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    success: int = 1,
) -> None:
    """Audit log kaydı - fire-and-forget, hata sessizce yutulur"""
    try:
        async with AsyncSessionLocal() as db:
            rec = AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                user_email=user_email,
                action=action,
                resource=resource,
                resource_id=str(resource_id) if resource_id is not None else None,
                details=details,
                ip_address=ip_address,
                user_agent=(user_agent or "")[:512] if user_agent else None,
                success=success,
            )
            db.add(rec)
            await db.commit()
    except Exception:
        pass
