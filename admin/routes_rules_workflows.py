"""
Admin paneli – Kurallar, iş akışları, process-config, training, chat-audits.
"""
import csv
import io
import json

from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy import select, desc, func

from models.database import AsyncSessionLocal
from models import ResponseRule, Tenant, AITrainingExample, ChatAudit, Message, Conversation

from admin.common import templates, _session_get, get_tenant_id
from admin import helpers

router = APIRouter()
require_module = helpers.require_module
PAGE_SIZE = helpers.PAGE_SIZE


# --- Kurallar ---

@router.get("/rules", response_class=HTMLResponse)
async def rules_list(request: Request):
    """Kurallar listeler. [GET /rules]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    page = max(1, int(request.query_params.get("page") or 1))
    async with AsyncSessionLocal() as db:
        count_q = select(func.count(ResponseRule.id)).where(ResponseRule.tenant_id == tid)
        total = (await db.execute(count_q)).scalar() or 0
        result = await db.execute(
            select(ResponseRule)
            .where(ResponseRule.tenant_id == tid)
            .order_by(desc(ResponseRule.priority), ResponseRule.id)
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        )
        rules = result.scalars().all()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return templates.TemplateResponse("rules.html", {
        "request": request,
        "rules": rules,
        "page": page,
        "total_pages": total_pages,
        "total": total,
    })


def _rule_image_urls_display(rule) -> str:
    """Kuralın image_urls JSON'ını satır satır metne çevirir (formda göstermek için)."""
    if not rule or not (rule.image_urls or "").strip():
        return ""
    raw = (rule.image_urls or "").strip()
    if raw in ("[]", ""):
        return ""
    try:
        arr = json.loads(raw)
        if isinstance(arr, list):
            return "\n".join(str(u).strip() for u in arr if u)
    except (json.JSONDecodeError, TypeError):
        pass
    return raw


def _rule_product_ids_display(rule) -> str:
    """Kuralın product_ids JSON'ını virgüllü metne çevirir (formda göstermek için)."""
    if not rule or not (rule.product_ids or "").strip():
        return ""
    raw = (rule.product_ids or "").strip()
    if raw in ("[]", ""):
        return ""
    try:
        arr = json.loads(raw)
        if isinstance(arr, list):
            return ", ".join(str(x) for x in arr)
    except (json.JSONDecodeError, TypeError):
        pass
    return raw


@router.get("/rules/new", response_class=HTMLResponse)
async def rule_new(request: Request):
    """Kural yeni oluşturma formu. [GET /rules/new]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("rule_form.html", {
        "request": request,
        "rule": None,
        "image_urls_display": "",
        "product_ids_display": "",
    })


@router.get("/rules/{id}", response_class=HTMLResponse)
async def rule_edit(request: Request, id: int):
    """Kural düzenleme formu. [GET /rules/{id}]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ResponseRule).where(ResponseRule.id == id, ResponseRule.tenant_id == tid))
        rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404)
    return templates.TemplateResponse("rule_form.html", {
        "request": request,
        "rule": rule,
        "image_urls_display": _rule_image_urls_display(rule),
        "product_ids_display": _rule_product_ids_display(rule),
    })


def _normalize_product_ids(raw: str) -> str:
    """'1, 2, 3' veya '[1,2,3]' → JSON [1,2,3] string."""
    raw = (raw or "").strip()
    if not raw or raw == "[]":
        return "[]"
    if raw.startswith("["):
        try:
            json.loads(raw)
            return raw
        except json.JSONDecodeError:
            pass
    ids = []
    for part in raw.replace(",", " ").split():
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return json.dumps(ids) if ids else "[]"


def _normalize_image_urls(raw: str) -> str:
    """Satır veya virgülle ayrılmış URL'ler → JSON array string."""
    raw = (raw or "").strip()
    if not raw:
        return "[]"
    if raw.startswith("["):
        try:
            arr = json.loads(raw)
            if isinstance(arr, list):
                return json.dumps([str(u).strip() for u in arr if u and str(u).strip().startswith("http")])
        except json.JSONDecodeError:
            pass
    urls = []
    for line in raw.replace(",", "\n").splitlines():
        u = line.strip()
        if u and (u.startswith("http://") or u.startswith("https://")):
            urls.append(u)
    return json.dumps(urls) if urls else "[]"


@router.post("/rules/save")
async def rule_save(
    request: Request,
    id: str = Form(""),
    name: str = Form(""),
    trigger_type: str = Form("keyword"),
    trigger_value: str = Form(""),
    product_ids: str = Form("[]"),
    image_urls: str = Form("[]"),
    custom_message: str = Form(""),
    is_active: str = Form(""),
    priority: int = Form(0),
):
    """Kural kaydeder. [POST /rules/save]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    rule_id = int(id) if id and id.isdigit() else None
    tid = get_tenant_id(request)
    product_ids = _normalize_product_ids(product_ids)
    image_urls = _normalize_image_urls(image_urls)
    async with AsyncSessionLocal() as db:
        if rule_id:
            result = await db.execute(select(ResponseRule).where(ResponseRule.id == rule_id, ResponseRule.tenant_id == tid))
            rule = result.scalar_one_or_none()
            if not rule:
                raise HTTPException(404)
        else:
            rule = ResponseRule(tenant_id=tid)
            db.add(rule)
        rule.name = (name or "").strip() or "Kural"
        rule.trigger_type = trigger_type if trigger_type in ("vehicle_model", "keyword") else "keyword"
        rule.trigger_value = trigger_value.strip()
        rule.product_ids = product_ids
        rule.image_urls = image_urls
        rule.custom_message = (custom_message or "").strip()
        rule.is_active = (is_active == "on")
        rule.priority = priority
        await db.commit()
    return RedirectResponse(url="/admin/rules", status_code=302)


@router.post("/rules/{id}/delete")
async def rule_delete(request: Request, id: int):
    """Kural siler. [POST /rules/{id}/delete]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ResponseRule).where(ResponseRule.id == id, ResponseRule.tenant_id == tid))
        rule = result.scalar_one_or_none()
        if rule:
            await db.delete(rule)
            await db.commit()
    return RedirectResponse(url="/admin/rules", status_code=302)


# --- İş Akışları (Workflow Builder) ---

@router.get("/workflows", response_class=HTMLResponse)
async def workflows_list(request: Request):
    """İş akışları listeler. [GET /workflows]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    await require_module(request, "workflows")
    tid = get_tenant_id(request)
    platform_filter = request.query_params.get("platform", "")
    from services.workflow.service import list_workflows
    workflows = await list_workflows(tid, platform=platform_filter or None)
    return templates.TemplateResponse("workflows_list.html", {
        "request": request,
        "workflows": workflows,
        "platform_filter": platform_filter,
    })


@router.get("/workflows/new", response_class=HTMLResponse)
async def workflow_new(request: Request):
    """İş akışı yeni oluşturma formu. [GET /workflows/new]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    await require_module(request, "workflows")
    return templates.TemplateResponse("workflow_form.html", {
        "request": request,
        "workflow": None,
        "steps": [],
    })


@router.get("/workflows/{id}", response_class=HTMLResponse)
async def workflow_edit(request: Request, id: int):
    """İş akışı düzenleme formu. [GET /workflows/{id}]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    await require_module(request, "workflows")
    tid = get_tenant_id(request)
    from services.workflow.service import get_workflow, get_workflow_steps
    workflow = await get_workflow(tid, id)
    if not workflow:
        raise HTTPException(404, "İş akışı bulunamadı")
    steps = await get_workflow_steps(id)
    return templates.TemplateResponse("workflow_form.html", {
        "request": request,
        "workflow": workflow,
        "steps": steps,
    })


@router.post("/workflows/save")
async def workflow_save(
    request: Request,
    id: int = Form(None),
    platform: str = Form("whatsapp"),
    workflow_name: str = Form(""),
    description: str = Form(""),
    is_active: str = Form("on"),
):
    """İş akışı kaydeder. [POST /workflows/save]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    await require_module(request, "workflows")
    tid = get_tenant_id(request)
    from services.workflow.service import create_workflow, update_workflow
    if id:
        w = await update_workflow(tid, id, workflow_name=workflow_name or None, description=description or None, is_active=(is_active == "on"))
        if not w:
            raise HTTPException(404)
        return RedirectResponse(url=f"/admin/workflows/{id}", status_code=302)
    w = await create_workflow(tid, platform, workflow_name or "Yeni Akış", description)
    return RedirectResponse(url=f"/admin/workflows/{w.id}", status_code=302)


@router.post("/workflows/{id}/delete")
async def workflow_delete(request: Request, id: int):
    """İş akışı siler. [POST /workflows/{id}/delete]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    await require_module(request, "workflows")
    tid = get_tenant_id(request)
    from services.workflow.service import delete_workflow
    await delete_workflow(tid, id)
    return RedirectResponse(url="/admin/workflows", status_code=302)


@router.post("/workflows/{id}/steps/add")
async def workflow_step_add(
    request: Request,
    id: int,
    step_name: str = Form(""),
    step_type: str = Form("action"),
    order_index: int = Form(0),
    step_config: str = Form(""),
):
    """İş akışı endpoint'i. [POST /workflows/{id}/steps/add]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    await require_module(request, "workflows")
    tid = get_tenant_id(request)
    from services.workflow.service import get_workflow, add_workflow_step
    w = await get_workflow(tid, id)
    if not w:
        raise HTTPException(404)
    config = None
    if step_config and step_config.strip():
        try:
            config = json.loads(step_config.strip())
        except json.JSONDecodeError:
            pass
    await add_workflow_step(id, step_name or "Yeni Adım", step_type, config=config, order_index=order_index)
    return RedirectResponse(url=f"/admin/workflows/{id}", status_code=302)


@router.post("/workflows/steps/{step_id}/update")
async def workflow_step_update(
    request: Request,
    step_id: int,
    step_name: str = Form(""),
    step_config: str = Form(""),
):
    """İş akışı günceller. [POST /workflows/steps/{step_id}/update]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    await require_module(request, "workflows")
    from services.workflow.service import update_workflow_step
    config = None
    if step_config is not None:
        s_stripped = step_config.strip()
        if s_stripped:
            try:
                config = json.loads(s_stripped)
            except json.JSONDecodeError:
                pass
        else:
            config = {}
    s = await update_workflow_step(step_id, step_name=step_name or None, config=config)
    wf_id = s.workflow_id if s else None
    ref = request.headers.get("referer") or (f"/admin/workflows/{wf_id}" if wf_id else "/admin/workflows")
    return RedirectResponse(url=ref, status_code=302)


@router.post("/workflows/steps/{step_id}/delete")
async def workflow_step_delete(request: Request, step_id: int):
    """İş akışı siler. [POST /workflows/steps/{step_id}/delete]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    await require_module(request, "workflows")
    from services.workflow.service import delete_workflow_step
    await delete_workflow_step(step_id)
    ref = request.headers.get("referer", "/admin/workflows")
    return RedirectResponse(url=ref, status_code=302)


@router.get("/workflows/{id}/builder", response_class=HTMLResponse)
async def workflow_builder(request: Request, id: int):
    """Görsel akış builder - Drag & Drop"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    await require_module(request, "workflows")
    tid = get_tenant_id(request)
    from services.workflow.service import get_workflow, get_workflow_graph
    data = await get_workflow_graph(tid, id)
    if not data:
        raise HTTPException(404, "İş akışı bulunamadı")
    return templates.TemplateResponse("workflow_builder.html", {
        "request": request,
        "workflow": data["workflow"],
        "workflow_id": id,
    })


@router.get("/workflows/{id}/graph")
async def workflow_graph_api(request: Request, id: int):
    """Grafik verisi JSON API"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    await require_module(request, "workflows")
    tid = get_tenant_id(request)
    from services.workflow.service import get_workflow_graph
    data = await get_workflow_graph(tid, id)
    if not data:
        raise HTTPException(404)
    return data


@router.post("/workflows/{id}/graph")
async def workflow_graph_save(request: Request, id: int):
    """Grafik kaydet JSON API"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    await require_module(request, "workflows")
    tid = get_tenant_id(request)
    body = await request.json()
    from services.workflow.service import save_workflow_graph
    ok = await save_workflow_graph(tid, id, body)
    if not ok:
        raise HTTPException(404)
    return {"ok": True}


# --- Süreç Konfigürasyonu ---

@router.get("/process-config", response_class=HTMLResponse)
async def process_config_list(request: Request):
    """Süreç yapılandırması listeler. [GET /process-config]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    await require_module(request, "workflows")
    tid = get_tenant_id(request)
    from services.workflow.service import list_process_configs
    configs = await list_process_configs(tid)
    return templates.TemplateResponse("process_config_list.html", {
        "request": request,
        "configs": configs,
    })


@router.get("/process-config/edit", response_class=HTMLResponse)
async def process_config_edit(request: Request, platform: str = "whatsapp", process_type: str = "order_management"):
    """Süreç yapılandırması düzenleme formu. [GET /process-config/edit]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    await require_module(request, "workflows")
    tid = get_tenant_id(request)
    from services.workflow.service import get_or_create_process_config
    pc = await get_or_create_process_config(tid, process_type, platform)
    escalation = {}
    sla = {}
    notifications = []
    if pc.escalation_rules:
        try:
            escalation = json.loads(pc.escalation_rules)
        except Exception:
            pass
    if pc.sla_settings:
        try:
            sla = json.loads(pc.sla_settings)
        except Exception:
            pass
    if pc.notification_rules:
        try:
            notifications = json.loads(pc.notification_rules)
        except Exception:
            pass
    return templates.TemplateResponse("process_config_form.html", {
        "request": request,
        "config": pc,
        "escalation": escalation,
        "sla": sla,
        "notifications": notifications,
    })


@router.post("/process-config/save")
async def process_config_save(
    request: Request,
    config_id: int = Form(...),
    auto_response: str = Form("on"),
    escalation_after_seconds: str = Form("300"),
    sla_response_seconds: str = Form("60"),
    sla_resolution_hours: str = Form("24"),
):
    """Süreç yapılandırması kaydeder. [POST /process-config/save]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    await require_module(request, "workflows")
    tid = get_tenant_id(request)
    from services.workflow.service import update_process_config
    escalation = {"after_seconds": int(escalation_after_seconds or 300)}
    sla = {"response_time_seconds": int(sla_response_seconds or 60), "resolution_hours": int(sla_resolution_hours or 24)}
    await update_process_config(tid, config_id, auto_response=(auto_response == "on"), escalation_rules=escalation, sla_settings=sla)
    return RedirectResponse(url="/admin/process-config", status_code=302)


# --- AI Eğitim (Örnek Soru-Cevap) + Chat Audits ---

@router.post("/training/quick-reply-options/save")
async def training_quick_reply_options_save(request: Request):
    """Soru seçeneklerini (quick reply) tenant ayarlarına kaydet."""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    form = await request.form()
    enabled = form.get("options_enabled") == "on"
    labels = form.getlist("opt_label")
    texts = form.getlist("opt_text")
    options = []
    for i, label in enumerate(labels):
        text = texts[i] if i < len(texts) else ""
        label = (label or "").strip()
        text = (text or "").strip()
        if label or text:
            options.append({"label": label or text, "text": text or label})
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.id == tid))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(404)
        existing = {}
        if tenant.settings:
            try:
                existing = json.loads(tenant.settings)
            except json.JSONDecodeError:
                existing = {}
        existing["quick_reply_options"] = {"enabled": enabled, "options": options}
        from services.core.crypto import encrypt_tenant_settings
        tenant.settings = json.dumps(encrypt_tenant_settings(existing), ensure_ascii=False)
        await db.commit()
    from services.core.cache import invalidate_tenant_cache
    await invalidate_tenant_cache(tid)
    return RedirectResponse(url="/admin/training?options_saved=1", status_code=302)


@router.post("/training/response-rules/save")
async def training_response_rules_save(request: Request):
    """AI yanit kurallarini tenant ayarlarina kaydet. Her satir bir kural."""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    form = await request.form()
    raw = (form.get("ai_response_rules") or "").strip()
    rules = []
    for line in raw.splitlines():
        t = line.strip()
        if len(t) >= 3:
            rules.append({"text": t, "priority": 0})

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.id == tid))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(404)
        existing = {}
        if tenant.settings:
            try:
                existing = json.loads(tenant.settings)
            except json.JSONDecodeError:
                existing = {}
        existing["ai_response_rules"] = rules
        from services.core.crypto import encrypt_tenant_settings
        tenant.settings = json.dumps(encrypt_tenant_settings(existing), ensure_ascii=False)
        await db.commit()
    from services.core.cache import invalidate_tenant_cache
    await invalidate_tenant_cache(tid)
    return RedirectResponse(url="/admin/training?rules_saved=1", status_code=302)


@router.post("/chat-audits/toggle")
async def chat_audits_toggle(request: Request):
    """Sohbet denetimini aç/kapat (super_admin)"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    if not _session_get(request, "super_admin"):
        raise HTTPException(403, detail="Bu işlem için super admin yetkisi gerekir")
    form = await request.form()
    enabled = form.get("enabled") == "on"
    from services.core.settings import set_chat_audit_enabled
    set_chat_audit_enabled(enabled)
    next_url = (form.get("next") or "").strip()
    if next_url and next_url.startswith("/admin"):
        return RedirectResponse(url=f"{next_url}?audit_toggled=1", status_code=302)
    return RedirectResponse(url="/admin/chat-audits?toggled=1", status_code=302)


@router.get("/chat-audits", response_class=HTMLResponse)
async def chat_audits_list(request: Request):
    """Sohbet denetim sonuçları - asenkron AI kalite kontrolü"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    page = max(1, int(request.query_params.get("page") or 1))
    from services.core.settings import get_chat_audit_enabled, get_chat_audit_sample_rate
    audit_enabled = get_chat_audit_enabled()
    sample_rate = get_chat_audit_sample_rate()

    async with AsyncSessionLocal() as db:
        count_q = select(func.count(ChatAudit.id)).where(ChatAudit.tenant_id == tid)
        total = (await db.execute(count_q)).scalar() or 0
        result = await db.execute(
            select(ChatAudit)
            .where(ChatAudit.tenant_id == tid)
            .order_by(desc(ChatAudit.created_at))
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        )
        audits = result.scalars().all()

    passed_count = sum(1 for a in audits if a.passed)
    failed_count = len(audits) - passed_count
    avg_score = sum(a.score or 0 for a in audits) / len(audits) if audits else 0
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    return templates.TemplateResponse(
        "chat_audits.html",
        {
            "request": request,
            "audits": audits,
            "audit_enabled": audit_enabled,
            "sample_rate": sample_rate,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "avg_score": round(avg_score, 1),
            "is_super_admin": _session_get(request, "super_admin"),
            "toggled": request.query_params.get("toggled") == "1",
            "page": page,
            "total_pages": total_pages,
            "total": total,
        },
    )


@router.get("/training", response_class=HTMLResponse)
async def training_list(request: Request):
    """Eğitim verisi listeler. [GET /training]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    from services.core.tenant import get_tenant_settings
    tenant_settings = await get_tenant_settings(tid)
    welcome_cfg = tenant_settings.get("welcome_scenarios") if isinstance(tenant_settings, dict) else {}
    if not isinstance(welcome_cfg, dict):
        welcome_cfg = {}
    sector_examples = welcome_cfg.get("sector_examples") if isinstance(welcome_cfg.get("sector_examples"), dict) else {}
    intro_variants = welcome_cfg.get("intro_variants") if isinstance(welcome_cfg.get("intro_variants"), list) else []
    def _to_multiline(items):
        if not isinstance(items, list):
            return ""
        lines = []
        for x in items:
            if isinstance(x, str):
                v = x.strip()
                if v:
                    lines.append(v)
        return "\n".join(lines)
    page = max(1, int(request.query_params.get("page") or 1))
    async with AsyncSessionLocal() as db:
        count_q = select(func.count(AITrainingExample.id)).where(AITrainingExample.tenant_id == tid)
        total_examples = (await db.execute(count_q)).scalar() or 0
        result = await db.execute(
            select(AITrainingExample)
            .where(AITrainingExample.tenant_id == tid)
            .order_by(desc(AITrainingExample.priority), desc(AITrainingExample.id))
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        )
        examples = result.scalars().all()
    total_pages = max(1, (total_examples + PAGE_SIZE - 1) // PAGE_SIZE)
    ai_rules = tenant_settings.get("ai_response_rules") or []
    if not isinstance(ai_rules, list):
        ai_rules = []
    ai_rules_text = "\n".join(
        (r.get("text") or "").strip() for r in ai_rules if isinstance(r, dict) and (r.get("text") or "").strip()
    )

    quick_reply_cfg = tenant_settings.get("quick_reply_options") or {}
    if not isinstance(quick_reply_cfg, dict):
        quick_reply_cfg = {}
    quick_reply_options = quick_reply_cfg.get("options") or []
    if not isinstance(quick_reply_options, list):
        quick_reply_options = []
    quick_reply_enabled = bool(quick_reply_cfg.get("enabled", True))

    return templates.TemplateResponse(
        "training_list.html",
        {
            "request": request,
            "examples": examples,
            "ai_response_rules_text": ai_rules_text,
            "rules_saved": request.query_params.get("rules_saved") == "1",
            "quick_reply_options": quick_reply_options,
            "quick_reply_enabled": quick_reply_enabled,
            "options_saved": request.query_params.get("options_saved") == "1",
            "welcome_enabled": bool(welcome_cfg.get("enabled", True)),
            "welcome_intro_variants_text": _to_multiline(intro_variants),
            "welcome_examples_general_text": _to_multiline(sector_examples.get("genel", [])),
            "welcome_examples_automotive_text": _to_multiline(sector_examples.get("otomotiv", [])),
            "welcome_examples_ecommerce_text": _to_multiline(sector_examples.get("e_ticaret", [])),
            "welcome_examples_health_text": _to_multiline(sector_examples.get("saglik", [])),
            "welcome_examples_education_text": _to_multiline(sector_examples.get("egitim", [])),
            "welcome_examples_tourism_text": _to_multiline(sector_examples.get("turizm", [])),
            "welcome_saved": request.query_params.get("welcome_saved") == "1",
            "page": page,
            "total_pages": total_pages,
            "total": total_examples,
        },
    )


@router.post("/training/welcome-scenarios/save")
async def training_welcome_scenarios_save(request: Request):
    """Ilk karsilama metni ve sektor bazli soru orneklerini tenant bazli kaydet."""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    form = await request.form()

    def _split_lines(raw: str) -> list:
        out = []
        for line in (raw or "").splitlines():
            val = line.strip()
            if len(val) >= 8:
                out.append(val)
        return out

    enabled = (form.get("welcome_enabled") == "on")
    intro_variants = _split_lines((form.get("welcome_intro_variants") or "").strip())
    examples_by_sector = {
        "genel": _split_lines((form.get("welcome_examples_general") or "").strip()),
        "otomotiv": _split_lines((form.get("welcome_examples_automotive") or "").strip()),
        "e_ticaret": _split_lines((form.get("welcome_examples_ecommerce") or "").strip()),
        "saglik": _split_lines((form.get("welcome_examples_health") or "").strip()),
        "egitim": _split_lines((form.get("welcome_examples_education") or "").strip()),
        "turizm": _split_lines((form.get("welcome_examples_tourism") or "").strip()),
    }

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.id == tid))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(404)
        existing = {}
        if tenant.settings:
            try:
                existing = json.loads(tenant.settings)
            except json.JSONDecodeError:
                existing = {}

        existing["welcome_scenarios"] = {
            "enabled": bool(enabled),
            "intro_variants": intro_variants,
            "sector_examples": examples_by_sector,
        }
        from services.core.crypto import encrypt_tenant_settings
        tenant.settings = json.dumps(encrypt_tenant_settings(existing), ensure_ascii=False)
        await db.commit()
    from services.core.cache import invalidate_tenant_cache
    await invalidate_tenant_cache(tid)
    return RedirectResponse(url="/admin/training?welcome_saved=1", status_code=302)


@router.post("/training/welcome-scenarios/preview")
async def training_welcome_scenarios_preview(request: Request):
    """Formdaki mevcut degerlerle ilk karsilama mesajinin onizlemesini dondur."""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    sector = (body.get("sector") or "genel").strip().lower()
    user_message = (body.get("user_message") or "merhaba").strip()
    intro_raw = body.get("intro_variants") or []
    sector_raw = body.get("sector_examples") or {}

    def _to_lines(val):
        if isinstance(val, str):
            return [x.strip() for x in val.splitlines() if x.strip() and len(x.strip()) >= 8]
        if isinstance(val, list):
            return [str(x).strip() for x in val if isinstance(x, str) and x.strip() and len(str(x).strip()) >= 8]
        return []

    intro_variants = _to_lines(intro_raw)
    sector_examples = {}
    for k, v in (sector_raw if isinstance(sector_raw, dict) else {}).items():
        lines = _to_lines(v)
        if lines:
            sector_examples[str(k)] = lines

    welcome_scenarios = {
        "enabled": True,
        "intro_variants": intro_variants,
        "sector_examples": sector_examples,
    }
    from services.core.tenant import get_tenant_settings
    tenant_settings = await get_tenant_settings(tid)
    tenant_name = tenant_settings.get("name", "Emare Asistan")

    async with AsyncSessionLocal() as db:
        from integrations.chat_handler import ChatHandler
        handler = ChatHandler(db)
        preview_text = handler._enhance_first_reply_for_sales(
            reply_text="",
            tenant_name=tenant_name,
            user_message=user_message,
            variant_seed=42,
            welcome_scenarios=welcome_scenarios,
            sector_override=sector if sector else None,
        )
    return JSONResponse({"preview": preview_text})


@router.post("/training/sync-embeddings")
async def training_sync_embeddings(request: Request):
    """Mevcut eğitim örnekleri için embedding oluştur (benzerlik araması için)"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    count = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AITrainingExample).where(
                AITrainingExample.tenant_id == tid,
                AITrainingExample.is_active == True,
            )
        )
        examples = result.scalars().all()
        try:
            from services.ai.embeddings import get_embedding
            from services.ai.vector_store import is_vector_available, upsert_training_embedding
            if await is_vector_available(db):
                for ex in examples:
                    emb = await get_embedding(ex.question)
                    if emb:
                        await upsert_training_embedding(db, ex.id, ex.question, ex.expected_answer, emb, tid)
                        count += 1
        except Exception:
            pass
    return RedirectResponse(url=f"/admin/training?synced={count}", status_code=302)


@router.get("/training/import", response_class=HTMLResponse)
async def training_import_get(request: Request):
    """Eğitim verisi endpoint'i. [GET /training/import]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("training_import.html", {"request": request})


@router.post("/training/import", response_class=HTMLResponse)
async def training_import_post(request: Request):
    """Eğitim verisi endpoint'i. [POST /training/import]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    form = await request.form()
    file = form.get("file")
    skip_header = form.get("skip_header") == "on"
    imported = 0
    errors = []
    if not file or not hasattr(file, "file"):
        errors.append("CSV dosyası seçilmedi.")
    else:
        try:
            content = (await file.read()).decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(content))
            async with AsyncSessionLocal() as db:
                for row in reader:
                    q = (row.get("question") or row.get("soru") or "").strip()
                    a = (row.get("expected_answer") or row.get("cevap") or "").strip()
                    if not q or not a:
                        continue
                    ex = AITrainingExample(tenant_id=tid)
                    ex.question = q
                    ex.expected_answer = a
                    ex.category = (row.get("category") or "").strip() or None
                    ex.trigger_keywords = (row.get("trigger_keywords") or "").strip() or None
                    try:
                        ex.priority = int(row.get("priority", 0) or 0)
                    except (ValueError, TypeError):
                        ex.priority = 0
                    ex.is_active = True
                    db.add(ex)
                    imported += 1
                await db.commit()
                if imported > 0:
                    from services.ai.vector_store import is_vector_available, upsert_training_embedding
                    from services.ai.embeddings import get_embedding
                    if await is_vector_available(db):
                        result = await db.execute(
                            select(AITrainingExample)
                            .where(AITrainingExample.tenant_id == tid)
                            .order_by(desc(AITrainingExample.id))
                            .limit(imported)
                        )
                        for ex in reversed(result.scalars().all()):
                            try:
                                emb = await get_embedding(ex.question)
                                if emb:
                                    await upsert_training_embedding(db, ex.id, ex.question, ex.expected_answer, emb, tid)
                            except Exception:
                                pass
        except Exception as e:
            errors.append(str(e))
    return templates.TemplateResponse("training_import.html", {
        "request": request,
        "imported": imported if not errors else None,
        "errors": errors if errors else None,
    })


@router.get("/training/new", response_class=HTMLResponse)
async def training_new(request: Request):
    """Eğitim verisi yeni oluşturma formu. [GET /training/new]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("training_form.html", {"request": request, "example": None})


@router.get("/training/{id}", response_class=HTMLResponse)
async def training_edit(request: Request, id: int):
    """Eğitim verisi düzenleme formu. [GET /training/{id}]"""
    if request.session.get("admin") != "ok":
        return RedirectResponse(url="/admin", status_code=302)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AITrainingExample).where(AITrainingExample.id == id, AITrainingExample.tenant_id == tid))
        example = result.scalar_one_or_none()
    if not example:
        raise HTTPException(404)
    return templates.TemplateResponse("training_form.html", {"request": request, "example": example})


@router.post("/training/save")
async def training_save(
    request: Request,
    id: str = Form(""),
    question: str = Form(""),
    expected_answer: str = Form(""),
    category: str = Form(""),
    trigger_keywords: str = Form(""),
    is_active: str = Form(""),
    priority: int = Form(0),
):
    """Eğitim verisi kaydeder. [POST /training/save]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    if not question.strip() or not expected_answer.strip():
        raise HTTPException(400, detail="Soru ve cevap alanları zorunludur")
    example_id = int(id) if id and id.isdigit() else None
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        if example_id:
            result = await db.execute(select(AITrainingExample).where(AITrainingExample.id == example_id, AITrainingExample.tenant_id == tid))
            example = result.scalar_one_or_none()
            if not example:
                raise HTTPException(404)
        else:
            example = AITrainingExample(tenant_id=tid)
            db.add(example)
        example.question = question.strip()
        example.expected_answer = expected_answer.strip()
        example.category = category.strip() or None
        example.trigger_keywords = trigger_keywords.strip() or None
        example.is_active = (is_active == "on")
        example.priority = priority
        await db.commit()
        await db.refresh(example)
        try:
            from services.ai.vector_store import delete_embeddings_by_meta, is_vector_available, upsert_training_embedding, SOURCE_AI_TRAINING
            if not example.is_active:
                await delete_embeddings_by_meta(db, SOURCE_AI_TRAINING, "training_example_id", example.id)
            elif await is_vector_available(db):
                from services.ai.embeddings import get_embedding
                emb = await get_embedding(example.question)
                if emb:
                    await upsert_training_embedding(
                        db, example.id, example.question, example.expected_answer,
                        emb, tid,
                    )
        except Exception:
            pass
    return RedirectResponse(url="/admin/training", status_code=302)


@router.post("/training/{id}/delete")
async def training_delete(request: Request, id: int):
    """Eğitim verisi siler. [POST /training/{id}/delete]"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AITrainingExample).where(AITrainingExample.id == id, AITrainingExample.tenant_id == tid))
        example = result.scalar_one_or_none()
        if example:
            try:
                from services.ai.vector_store import delete_embeddings_by_meta, SOURCE_AI_TRAINING
                await delete_embeddings_by_meta(db, SOURCE_AI_TRAINING, "training_example_id", id)
            except Exception:
                pass
            await db.delete(example)
            await db.commit()
    return RedirectResponse(url="/admin/training", status_code=302)


@router.post("/training/from-chat")
async def training_from_chat(request: Request, message_id: str = Form(...)):
    """Sohbet mesajından eğitim örneği oluştur - önceki user + bu assistant mesajı"""
    if request.session.get("admin") != "ok":
        raise HTTPException(401)
    tid = get_tenant_id(request)
    try:
        mid = int(message_id)
    except (ValueError, TypeError):
        raise HTTPException(400, detail="Geçersiz mesaj ID")
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Message).where(Message.id == mid, Message.role == "assistant")
        )
        msg = result.scalar_one_or_none()
        if not msg or not msg.content:
            raise HTTPException(404, detail="Mesaj bulunamadı")
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == msg.conversation_id, Conversation.tenant_id == tid)
        )
        if not conv_result.scalar_one_or_none():
            raise HTTPException(404)
        prev_result = await db.execute(
            select(Message)
            .where(
                Message.conversation_id == msg.conversation_id,
                Message.role == "user",
                Message.id < msg.id,
            )
            .order_by(Message.id.desc())
            .limit(1)
        )
        prev_msg = prev_result.scalar_one_or_none()
        if not prev_msg or not (prev_msg.content or "").strip():
            raise HTTPException(400, detail="Önceki müşteri mesajı bulunamadı")
        content = (msg.content or "").replace("\n[Ürün resimleri gönderildi]", "").replace("[Ürün resimleri gönderildi]", "").strip()
        if len(content) < 5:
            raise HTTPException(400, detail="Asistan yanıtı çok kısa")
        ex = AITrainingExample(tenant_id=tid)
        ex.question = (prev_msg.content or "").strip()
        ex.expected_answer = content
        ex.is_active = True
        db.add(ex)
        await db.commit()
        await db.refresh(ex)
        try:
            from services.ai.vector_store import is_vector_available, upsert_training_embedding
            from services.ai.embeddings import get_embedding
            if await is_vector_available(db):
                emb = await get_embedding(ex.question)
                if emb:
                    await upsert_training_embedding(db, ex.id, ex.question, ex.expected_answer, emb, tid)
        except Exception:
            pass
    return RedirectResponse(url="/admin/training?from_chat=1", status_code=302)
