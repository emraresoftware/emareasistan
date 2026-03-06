"""
Workflow Engine - ChatHandler'da mesaj geldiğinde tenant workflow'larını çalıştırır.
Trigger → Condition → Action yapısı ile akışları değerlendirir.
"""
import json
import logging
from typing import Any

from models.database import AsyncSessionLocal
from models import TenantWorkflow, WorkflowStep
from sqlalchemy import select

logger = logging.getLogger("workflow_engine")


async def get_active_workflows_for_platform(
    tenant_id: int,
    platform: str,
) -> list[tuple[TenantWorkflow, list[WorkflowStep]]]:
    """Platform için aktif workflow'ları ve adımlarını getir."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TenantWorkflow)
            .where(
                TenantWorkflow.tenant_id == tenant_id,
                TenantWorkflow.platform == platform,
                TenantWorkflow.is_active == True,
            )
        )
        workflows = list(result.scalars().all())
        out = []
        for w in workflows:
            steps_result = await db.execute(
                select(WorkflowStep)
                .where(WorkflowStep.workflow_id == w.id)
                .order_by(WorkflowStep.order_index, WorkflowStep.id)
            )
            steps = list(steps_result.scalars().all())
            if steps:
                out.append((w, steps))
        return out


def _parse_step_config(step: WorkflowStep) -> dict[str, Any]:
    """Adım config'ini parse et."""
    if not step.config:
        return {}
    try:
        return json.loads(step.config) if isinstance(step.config, str) else (step.config or {})
    except (json.JSONDecodeError, TypeError):
        return {}


def _trigger_matches(
    step: WorkflowStep,
    message_text: str,
    msg_lower: str,
) -> bool:
    """Trigger adımı mesajla eşleşiyor mu?"""
    config = _parse_step_config(step)
    trigger_type = config.get("type") or "message_received"
    if trigger_type == "message_received":
        return True
    if trigger_type == "keyword":
        keywords = config.get("keywords") or []
        if isinstance(keywords, str):
            keywords = [k.strip().lower() for k in keywords.split(",") if k.strip()]
        return any(kw in msg_lower for kw in keywords)
    return False


def _condition_passes(
    step: WorkflowStep,
    msg_lower: str,
) -> bool:
    """Condition adımı geçiyor mu? True = devam et."""
    config = _parse_step_config(step)
    keywords = config.get("keywords") or []
    if isinstance(keywords, str):
        keywords = [k.strip().lower() for k in keywords.split(",") if k.strip()]
    if not keywords:
        return True
    return any(kw in msg_lower for kw in keywords)


def _get_action_response(step: WorkflowStep) -> dict | None:
    """
    Action adımından yanıt al. None = normal akışa devam et.
    Returns: {"text": "...", "product_images": [...]} veya None
    """
    config = _parse_step_config(step)
    action_type = config.get("type") or "ai_response"
    if action_type == "template":
        text = config.get("text") or ""
        if text:
            return {"text": text.strip()}
    return None


async def run_workflows(
    tenant_id: int,
    platform: str,
    message_text: str,
    msg_lower: str,
) -> dict | None:
    """
    Mesaj için aktif workflow'ları çalıştır.
    Bir workflow template yanıtı döndürürse o yanıtı ver.
    Hiçbiri dönmezse None (normal ChatHandler akışı devam eder).
    """
    workflows = await get_active_workflows_for_platform(tenant_id, platform)
    if not workflows:
        return None

    for workflow, steps in workflows:
        if not steps:
            continue
        # İlk adım trigger olmalı
        first = steps[0]
        if first.step_type != "trigger":
            continue
        if not _trigger_matches(first, message_text or "", msg_lower or ""):
            continue

        # Adımları sırayla işle (trigger'dan sonra)
        for step in steps[1:]:
            if step.step_type == "condition":
                if not _condition_passes(step, msg_lower or ""):
                    break  # Bu workflow'dan çık, sonrakine geç
            elif step.step_type == "action":
                response = _get_action_response(step)
                if response:
                    logger.info(
                        "Workflow %s (%s) template yanıtı döndürdü",
                        workflow.workflow_name,
                        workflow.id,
                    )
                    return response
                # ai_response / continue → döngü devam, normal akışa düşecek

    return None
