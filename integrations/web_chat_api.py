"""
Web Sohbet API - Firmaların sitelerine gömülebilen AI destekli sohbet
POST /api/chat/web - mesaj gönder, AI yanıtı al
GET /chat/{tenant_slug} - iframe için tam sayfa sohbet arayüzü
"""
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models.database import AsyncSessionLocal
from models import Tenant
from integrations import ChatHandler
from services.core.modules import get_enabled_modules, is_module_enabled

logger = logging.getLogger(__name__)

router = APIRouter(tags=["web_chat"])
template_dir = Path(__file__).resolve().parent.parent / "admin" / "templates"
templates = Jinja2Templates(directory=str(template_dir))


class WebChatRequest(BaseModel):
    tenant_slug: str
    visitor_id: str
    message: str
    customer_name: str | None = None


@router.post("/api/chat/web")
async def web_chat_send(request: WebChatRequest):
    """
    Web sohbette ziyaretçi mesajı gönder, AI yanıtı al.
    Harici sitelerden (embed) erişilebilir - CORS açık olmalı.
    """
    if not (request.message or "").strip():
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Tenant).where(
                Tenant.slug == request.tenant_slug,
                Tenant.status == "active",
            )
        )
        tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Firma bulunamadı")

    mods = await get_enabled_modules(tenant.id)
    if not is_module_enabled(mods, "web_chat"):
        raise HTTPException(status_code=403, detail="Web sohbet bu firma için etkin değil")

    async with AsyncSessionLocal() as db:
        handler = ChatHandler(db)
        response = await handler.process_message(
            platform="web",
            user_id=request.visitor_id,
            message_text=(request.message or "").strip(),
            conversation_history=[],
            customer_name=request.customer_name,
            tenant_id=tenant.id,
        )

    return {
        "text": response.get("text", ""),
        "image_url": response.get("image_url"),
        "image_caption": response.get("image_caption"),
        "product_images": response.get("product_images", []),
        "suggested_products": response.get("suggested_products", []),
        "suggest_replies": response.get("suggest_replies", []),
        "location": response.get("location"),
        "videos": response.get("videos", []),
    }


@router.get("/chat/{tenant_slug}", response_class=HTMLResponse)
async def web_chat_page(request: Request, tenant_slug: str):
    """
    Ziyaretçi sohbet sayfası - iframe ile gömülebilir.
    Örnek: <iframe src="https://api.emareasistan.com/chat/firma-slug"></iframe>
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Tenant).where(
                Tenant.slug == tenant_slug,
                Tenant.status == "active",
            )
        )
        tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Firma bulunamadı")

    mods = await get_enabled_modules(tenant.id)
    if not is_module_enabled(mods, "web_chat"):
        raise HTTPException(status_code=403, detail="Web sohbet bu firma için etkin değil")

    settings = get_settings()
    api_base = settings.app_base_url.rstrip("/")

    return templates.TemplateResponse(
        "web_chat.html",
        {
            "request": request,
            "tenant": tenant,
            "tenant_slug": tenant_slug,
            "api_base": api_base,
        },
    )
