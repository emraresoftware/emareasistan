"""Kurum bazlı iş akışı ve süreç konfigürasyonu servisi"""
import json
from typing import Any

from models.database import AsyncSessionLocal
from models import TenantWorkflow, WorkflowStep, ProcessConfig
from sqlalchemy import select, desc


async def list_workflows(tenant_id: int, platform: str | None = None) -> list[TenantWorkflow]:
    """Kurumun iş akışlarını listele"""
    async with AsyncSessionLocal() as db:
        q = select(TenantWorkflow).where(TenantWorkflow.tenant_id == tenant_id)
        if platform:
            q = q.where(TenantWorkflow.platform == platform)
        q = q.order_by(desc(TenantWorkflow.updated_at))
        result = await db.execute(q)
        return list(result.scalars().all())


async def get_workflow(tenant_id: int, workflow_id: int) -> TenantWorkflow | None:
    """Tek iş akışı getir"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TenantWorkflow)
            .where(TenantWorkflow.id == workflow_id, TenantWorkflow.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()


async def get_workflow_steps(workflow_id: int) -> list[WorkflowStep]:
    """İş akışı adımlarını getir"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WorkflowStep)
            .where(WorkflowStep.workflow_id == workflow_id)
            .order_by(WorkflowStep.order_index, WorkflowStep.id)
        )
        return list(result.scalars().all())


async def create_workflow(
    tenant_id: int,
    platform: str,
    workflow_name: str,
    description: str = "",
) -> TenantWorkflow:
    """Yeni iş akışı oluştur"""
    async with AsyncSessionLocal() as db:
        w = TenantWorkflow(
            tenant_id=tenant_id,
            platform=platform,
            workflow_name=workflow_name,
            description=description or None,
        )
        db.add(w)
        await db.commit()
        await db.refresh(w)
        return w


async def update_workflow(
    tenant_id: int,
    workflow_id: int,
    workflow_name: str | None = None,
    description: str | None = None,
    is_active: bool | None = None,
) -> TenantWorkflow | None:
    """İş akışı güncelle"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TenantWorkflow)
            .where(TenantWorkflow.id == workflow_id, TenantWorkflow.tenant_id == tenant_id)
        )
        w = result.scalar_one_or_none()
        if not w:
            return None
        if workflow_name is not None:
            w.workflow_name = workflow_name
        if description is not None:
            w.description = description
        if is_active is not None:
            w.is_active = is_active
        await db.commit()
        await db.refresh(w)
        return w


async def delete_workflow(tenant_id: int, workflow_id: int) -> bool:
    """İş akışı sil (adımlar CASCADE ile silinir)"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TenantWorkflow)
            .where(TenantWorkflow.id == workflow_id, TenantWorkflow.tenant_id == tenant_id)
        )
        w = result.scalar_one_or_none()
        if not w:
            return False
        await db.delete(w)
        await db.commit()
        return True


async def add_workflow_step(
    workflow_id: int,
    step_name: str,
    step_type: str,
    config: dict[str, Any] | None = None,
    order_index: int = 0,
) -> WorkflowStep:
    """İş akışına adım ekle"""
    async with AsyncSessionLocal() as db:
        s = WorkflowStep(
            workflow_id=workflow_id,
            step_name=step_name,
            step_type=step_type,
            config=json.dumps(config) if config else None,
            order_index=order_index,
        )
        db.add(s)
        await db.commit()
        await db.refresh(s)
        return s


async def update_workflow_step(
    step_id: int,
    step_name: str | None = None,
    step_type: str | None = None,
    config: dict[str, Any] | None = None,
    order_index: int | None = None,
) -> WorkflowStep | None:
    """İş akışı adımı güncelle"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(WorkflowStep).where(WorkflowStep.id == step_id))
        s = result.scalar_one_or_none()
        if not s:
            return None
        if step_name is not None:
            s.step_name = step_name
        if step_type is not None:
            s.step_type = step_type
        if config is not None:
            s.config = json.dumps(config)
        if order_index is not None:
            s.order_index = order_index
        await db.commit()
        await db.refresh(s)
        return s


async def get_workflow_graph(tenant_id: int, workflow_id: int) -> dict | None:
    """İş akışı + adımlar + grafik layout (Drawflow import için)"""
    w = await get_workflow(tenant_id, workflow_id)
    if not w:
        return None
    steps = await get_workflow_steps(workflow_id)
    graph_layout = None
    if w.graph_layout:
        try:
            graph_layout = json.loads(w.graph_layout)
        except Exception:
            pass
    return {
        "workflow": {"id": w.id, "workflow_name": w.workflow_name, "platform": w.platform},
        "steps": [{"id": s.id, "step_name": s.step_name, "step_type": s.step_type, "config": s.config or "{}", "order_index": s.order_index or 0} for s in steps],
        "graph_layout": graph_layout,
    }


async def save_workflow_graph(tenant_id: int, workflow_id: int, drawflow_export: dict) -> bool:
    """Drawflow export'unu kaydet, order_index güncelle"""
    w = await get_workflow(tenant_id, workflow_id)
    if not w:
        return False
    steps = await get_workflow_steps(workflow_id)
    step_ids = {s.id for s in steps}

    try:
        data = drawflow_export.get("drawflow", {}).get("Home", {}).get("data", {})
    except Exception:
        data = {}

    # Drawflow node_id -> step_id eşlemesi (data.step_id)
    df_to_step = {}
    for nid_str, node in data.items():
        step_id = (node.get("data") or {}).get("step_id")
        if step_id and step_id in step_ids:
            nid = int(nid_str) if isinstance(nid_str, str) and nid_str.isdigit() else nid_str
            df_to_step[nid] = step_id

    # Edge'ler: Drawflow node_id -> [target Drawflow node_ids]
    out_edges = {}
    for nid_str, node in data.items():
        nid = int(nid_str) if isinstance(nid_str, str) and nid_str.isdigit() else nid_str
        if nid not in df_to_step:
            continue
        conns = node.get("outputs", {}).get("output_1", {}).get("connections", [])
        for c in conns:
            tgt = c.get("node")
            if tgt is not None:
                tgt_id = int(tgt) if isinstance(tgt, str) and str(tgt).isdigit() else tgt
                if tgt_id in df_to_step:
                    out_edges.setdefault(nid, []).append(tgt_id)

    # Topological sort (Drawflow node id'lere göre)
    df_ids = set(df_to_step.keys())
    in_degree = {nid: 0 for nid in df_ids}
    for src, tgts in out_edges.items():
        for t in tgts:
            in_degree[t] = in_degree.get(t, 0) + 1
    order_map = {}  # step_id -> order_index
    idx = 0
    remaining = set(df_ids)
    while remaining:
        roots = [nid for nid in remaining if in_degree.get(nid, 0) == 0]
        if not roots:
            for nid in remaining:
                order_map[df_to_step[nid]] = idx
                idx += 1
            break
        for nid in sorted(roots, key=lambda x: (x if isinstance(x, int) else 0)):
            order_map[df_to_step[nid]] = idx
            idx += 1
            remaining.discard(nid)
            for tgt in out_edges.get(nid, []):
                in_degree[tgt] = in_degree.get(tgt, 0) - 1

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(WorkflowStep).where(WorkflowStep.workflow_id == workflow_id))
        for s in result.scalars().all():
            s.order_index = order_map.get(s.id, s.order_index or 0)
        w_result = await db.execute(
            select(TenantWorkflow).where(TenantWorkflow.id == workflow_id, TenantWorkflow.tenant_id == tenant_id)
        )
        w_row = w_result.scalar_one_or_none()
        if w_row:
            w_row.graph_layout = json.dumps(drawflow_export)
        await db.commit()
    return True


async def get_workflow_graph_layout(workflow_id: int) -> dict | None:
    """İş akışı görsel layout (Drawflow JSON) getir"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TenantWorkflow.graph_layout).where(TenantWorkflow.id == workflow_id)
        )
        row = result.scalar_one_or_none()
        if not row or not row[0]:
            return None
        try:
            return json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return None


async def save_workflow_graph_layout(tenant_id: int, workflow_id: int, layout: dict) -> bool:
    """İş akışı görsel layout kaydet"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TenantWorkflow)
            .where(TenantWorkflow.id == workflow_id, TenantWorkflow.tenant_id == tenant_id)
        )
        w = result.scalar_one_or_none()
        if not w:
            return False
        w.graph_layout = json.dumps(layout)
        await db.commit()
        return True


async def delete_workflow_step(step_id: int) -> bool:
    """İş akışı adımı sil"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(WorkflowStep).where(WorkflowStep.id == step_id))
        s = result.scalar_one_or_none()
        if not s:
            return False
        await db.delete(s)
        await db.commit()
        return True


# --- ProcessConfig ---

async def list_process_configs(tenant_id: int, platform: str | None = None) -> list[ProcessConfig]:
    """Kurumun süreç konfigürasyonlarını listele"""
    async with AsyncSessionLocal() as db:
        q = select(ProcessConfig).where(ProcessConfig.tenant_id == tenant_id)
        if platform:
            q = q.where(ProcessConfig.platform == platform)
        q = q.order_by(ProcessConfig.platform, ProcessConfig.process_type)
        result = await db.execute(q)
        return list(result.scalars().all())


async def get_or_create_process_config(
    tenant_id: int,
    process_type: str,
    platform: str,
) -> ProcessConfig:
    """Süreç konfigürasyonu getir veya oluştur"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ProcessConfig)
            .where(
                ProcessConfig.tenant_id == tenant_id,
                ProcessConfig.process_type == process_type,
                ProcessConfig.platform == platform,
            )
        )
        pc = result.scalar_one_or_none()
        if pc:
            return pc
        pc = ProcessConfig(
            tenant_id=tenant_id,
            process_type=process_type,
            platform=platform,
        )
        db.add(pc)
        await db.commit()
        await db.refresh(pc)
        return pc


async def update_process_config(
    tenant_id: int,
    config_id: int,
    auto_response: bool | None = None,
    escalation_rules: dict | None = None,
    sla_settings: dict | None = None,
    notification_rules: list | None = None,
) -> ProcessConfig | None:
    """Süreç konfigürasyonu güncelle"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ProcessConfig)
            .where(ProcessConfig.id == config_id, ProcessConfig.tenant_id == tenant_id)
        )
        pc = result.scalar_one_or_none()
        if not pc:
            return None
        if auto_response is not None:
            pc.auto_response = auto_response
        if escalation_rules is not None:
            pc.escalation_rules = json.dumps(escalation_rules)
        if sla_settings is not None:
            pc.sla_settings = json.dumps(sla_settings)
        if notification_rules is not None:
            pc.notification_rules = json.dumps(notification_rules)
        await db.commit()
        await db.refresh(pc)
        return pc
