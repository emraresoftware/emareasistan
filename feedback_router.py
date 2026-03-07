"""
Emare Feedback Router — FastAPI Template v1.0
Kullanım:  from feedback_router import router as feedback_router
           app.include_router(feedback_router, prefix="/api/feedback")
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from src.models.database import Base, get_db
except ImportError:
    try:
        from models.database import Base, get_db
    except ImportError:
        from database import Base, get_db

router = APIRouter(tags=["feedback"])


# ── Model ────────────────────────────────────────────────────────────────
class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(100), nullable=True)
    message = Column(Text, nullable=False)
    category = Column(String(20), default="bug")       # bug|suggestion|question|other
    priority = Column(String(20), default="normal")    # low|normal|high|critical
    status = Column(String(20), default="open")        # open|in_progress|resolved|closed
    page_url = Column(String(500), nullable=True)
    admin_reply = Column(Text, nullable=True)
    replied_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    CATEGORY_LABELS = {"bug": "Hata", "suggestion": "Öneri", "question": "Soru", "other": "Diğer"}
    STATUS_LABELS = {"open": "Açık", "in_progress": "İnceleniyor", "resolved": "Çözüldü", "closed": "Kapatıldı"}

    def to_dict(self):
        return {
            "id": self.id,
            "message": self.message,
            "category": self.category,
            "category_label": self.CATEGORY_LABELS.get(self.category, self.category),
            "priority": self.priority,
            "status": self.status,
            "status_label": self.STATUS_LABELS.get(self.status, self.status),
            "page_url": self.page_url,
            "admin_reply": self.admin_reply,
            "replied_at": self.replied_at.isoformat() if self.replied_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── Şemalar ──────────────────────────────────────────────────────────────
class FeedbackCreate(BaseModel):
    message: str = Field(..., min_length=3, max_length=2000)
    category: str = Field("bug", pattern="^(bug|suggestion|question|other)$")
    priority: str = Field("normal", pattern="^(low|normal|high|critical)$")
    page_url: Optional[str] = None


class FeedbackReply(BaseModel):
    admin_reply: str = Field(..., min_length=2)
    status: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(open|in_progress|resolved|closed)$")


# ── Endpointler ──────────────────────────────────────────────────────────
@router.post("/", summary="Geri bildirim gönder")
async def create_feedback(
    body: FeedbackCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    fb = Feedback(
        message=body.message,
        category=body.category,
        priority=body.priority,
        page_url=body.page_url or str(request.url),
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)
    return {"success": True, "message": "Geri bildiriminiz alındı. Teşekkür ederiz!", "feedback": fb.to_dict()}


@router.get("/my", summary="Kullanıcının kendi bildirimleri")
async def my_feedbacks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Feedback).order_by(Feedback.created_at.desc()).limit(50)
    )
    feedbacks = result.scalars().all()
    return {"messages": [f.to_dict() for f in feedbacks]}


@router.get("/", summary="Tüm bildirimler (admin)")
async def list_feedbacks(
    status: Optional[str] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Feedback).order_by(Feedback.created_at.desc())
    if status:
        q = q.where(Feedback.status == status)
    if category:
        q = q.where(Feedback.category == category)
    result = await db.execute(q)
    feedbacks = result.scalars().all()

    total = len(feedbacks)
    open_count = sum(1 for f in feedbacks if f.status == "open")
    resolved = sum(1 for f in feedbacks if f.status == "resolved")

    return {
        "feedbacks": [f.to_dict() for f in feedbacks],
        "stats": {"total": total, "open": open_count, "resolved": resolved},
    }


@router.patch("/{feedback_id}/status", summary="Durum güncelle (admin)")
async def update_status(
    feedback_id: str,
    body: StatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    fb = result.scalar_one_or_none()
    if not fb:
        from fastapi import HTTPException
        raise HTTPException(404, "Bulunamadı")
    fb.status = body.status
    await db.commit()
    return {"success": True, "feedback": fb.to_dict()}


@router.post("/{feedback_id}/reply", summary="Admin yanıtı")
async def reply_feedback(
    feedback_id: str,
    body: FeedbackReply,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    fb = result.scalar_one_or_none()
    if not fb:
        from fastapi import HTTPException
        raise HTTPException(404, "Bulunamadı")
    fb.admin_reply = body.admin_reply
    fb.replied_at = datetime.utcnow()
    if body.status:
        fb.status = body.status
    elif fb.status == "open":
        fb.status = "in_progress"
    await db.commit()
    return {"success": True, "feedback": fb.to_dict()}
