"""
Dis sistemlerden modul bazli veri cekme (pull) servisi.
Ilk surum: contacts, products, orders, appointments, reminders, admin_staff.
"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from time import perf_counter
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    Contact,
    Product,
    Order,
    Appointment,
    Reminder,
    LeaveRequest,
    Invoice,
    PurchaseOrder,
)
from services.core.tenant import get_module_api_settings
from services.core.tracing import record_trace_event, check_trace_alarm


def _preview_record(row: dict[str, Any], max_fields: int = 8) -> dict[str, Any]:
    """
    UI preview icin kaydi sadeleştir.
    Uzun/karmaşık alanlar kisaltilir.
    """
    out: dict[str, Any] = {}
    for idx, (k, v) in enumerate(row.items()):
        if idx >= max_fields:
            break
        if isinstance(v, (dict, list)):
            try:
                out[k] = json.dumps(v, ensure_ascii=False)[:200]
            except Exception:
                out[k] = str(v)[:200]
        else:
            out[k] = str(v)[:200]
    return out


def _push_headers(cfg: dict, module_id: str) -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    api_key = (cfg.get("api_key") or cfg.get("erp_api_key") or "").strip()
    if api_key:
        auth_header = (cfg.get("auth_header") or "Authorization").strip()
        if auth_header.lower() == "authorization" and not api_key.lower().startswith("bearer "):
            headers[auth_header] = f"Bearer {api_key}"
        else:
            headers[auth_header] = api_key
    return headers


def _get_push_url(cfg: dict, module_id: str) -> str:
    if module_id == "orders":
        return (cfg.get("push_api_url") or cfg.get("erp_api_url") or cfg.get("api_url") or "").strip()
    return (cfg.get("push_api_url") or cfg.get("api_url") or "").strip()


def _parse_field_mapping(cfg: dict) -> dict[str, str]:
    raw = (cfg.get("field_mapping_json") or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items() if str(k).strip() and str(v).strip()}
    except Exception:
        pass
    return {}


def _apply_field_mapping(record: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    if not mapping:
        return record
    out: dict[str, Any] = {}
    for lk, lv in record.items():
        out[mapping.get(lk, lk)] = lv
    return out


def _reverse_mapping(mapping: dict[str, str]) -> dict[str, str]:
    return {remote: local for local, remote in mapping.items()}


def _apply_reverse_mapping(record: dict[str, Any], reverse_mapping: dict[str, str]) -> dict[str, Any]:
    if not reverse_mapping:
        return record
    out: dict[str, Any] = {}
    for rk, rv in record.items():
        out[reverse_mapping.get(rk, rk)] = rv
    return out


def _resolve_local_id_field(mapping: dict[str, str], remote_id_field: str, fallback: str) -> str:
    """
    mapping local->remote oldugundan, remote id alanina karsilik gelen local key'i bulur.
    """
    for local_key, remote_key in mapping.items():
        if remote_key == remote_id_field:
            return local_key
    return fallback


def _id_value(record: dict[str, Any], id_field: str) -> str:
    v = record.get(id_field)
    return str(v).strip() if v is not None else ""


def _conflict_should_skip(cfg: dict, local_row: dict[str, Any], remote_index: dict[str, dict], remote_id_field: str) -> bool:
    strategy = (cfg.get("conflict_strategy") or "last_write_wins").strip().lower()
    if strategy != "manual":
        return False
    key = _id_value(local_row, remote_id_field)
    if not key:
        return False
    remote = remote_index.get(key)
    if not remote:
        return False
    local_upd = _to_dt(local_row.get("updated_at"))
    remote_upd = _to_dt(remote.get("updated_at") or remote.get("updatedAt"))
    return bool(local_upd and remote_upd and remote_upd > local_upd)


def _dig_path(data: Any, path: str | None) -> Any:
    if not path:
        return data
    cur = data
    for part in path.split("."):
        key = part.strip()
        if not key:
            continue
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return None
    return cur


def _normalize_records(payload: Any, list_path: str | None) -> list[dict]:
    data = _dig_path(payload, list_path)
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("items", "data", "results", "records"):
            maybe = data.get(key)
            if isinstance(maybe, list):
                return [x for x in maybe if isinstance(x, dict)]
    return []


def _to_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


async def _fetch_remote_records(module_id: str, cfg: dict) -> list[dict]:
    if module_id == "orders":
        url = (cfg.get("erp_api_url") or cfg.get("api_url") or "").strip()
    else:
        url = (cfg.get("api_url") or "").strip()
    if not url:
        return []

    headers: dict[str, str] = {}
    api_key = (cfg.get("api_key") or cfg.get("erp_api_key") or "").strip()
    if api_key:
        auth_header = (cfg.get("auth_header") or "Authorization").strip()
        if auth_header.lower() == "authorization" and not api_key.lower().startswith("bearer "):
            headers[auth_header] = f"Bearer {api_key}"
        else:
            headers[auth_header] = api_key

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        payload = resp.json()

    list_path = (cfg.get("list_path") or "").strip() or None
    return _normalize_records(payload, list_path)


async def _fetch_admin_staff_payload(cfg: dict) -> Any:
    url = (cfg.get("api_url") or "").strip()
    if not url:
        raise ValueError("admin_staff api_url bos")
    headers: dict[str, str] = {}
    api_key = (cfg.get("api_key") or "").strip()
    if api_key:
        headers[(cfg.get("auth_header") or "Authorization").strip()] = (
            api_key if api_key.lower().startswith("bearer ") else f"Bearer {api_key}"
        )
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def _sync_contacts(db: AsyncSession, tenant_id: int, records: list[dict], cfg: dict | None = None) -> int:
    changed = 0
    for row in records:
        phone = str(row.get("phone") or row.get("mobile") or row.get("telephone") or "").strip()
        if not phone:
            continue
        name = str(row.get("name") or row.get("full_name") or row.get("customer_name") or "Isimsiz").strip()
        email = (row.get("email") or None)
        notes = (row.get("notes") or row.get("note") or None)
        result = await db.execute(select(Contact).where(Contact.tenant_id == tenant_id, Contact.phone == phone))
        c = result.scalar_one_or_none()
        if not c:
            c = Contact(tenant_id=tenant_id, phone=phone, name=name, email=email, notes=notes)
            db.add(c)
        else:
            if cfg and (cfg.get("conflict_strategy") or "").strip().lower() == "manual":
                local_upd = c.updated_at
                remote_upd = _to_dt(row.get("updated_at") or row.get("updatedAt"))
                if local_upd and remote_upd and local_upd > remote_upd:
                    continue
            c.name = name or c.name
            c.email = email or c.email
            c.notes = notes or c.notes
        changed += 1
    return changed


async def _sync_products(db: AsyncSession, tenant_id: int, records: list[dict], cfg: dict | None = None) -> int:
    changed = 0
    for row in records:
        name = str(row.get("name") or row.get("title") or "").strip()
        if not name:
            continue
        slug = str(row.get("slug") or row.get("code") or "").strip() or None
        result = None
        if slug:
            result = await db.execute(select(Product).where(Product.tenant_id == tenant_id, Product.slug == slug))
        p = result.scalar_one_or_none() if result else None
        if not p:
            result2 = await db.execute(select(Product).where(Product.tenant_id == tenant_id, Product.name == name))
            p = result2.scalar_one_or_none()
        if not p:
            p = Product(tenant_id=tenant_id, name=name)
            db.add(p)
        elif cfg and (cfg.get("conflict_strategy") or "").strip().lower() == "manual":
            local_upd = p.updated_at
            remote_upd = _to_dt(row.get("updated_at") or row.get("updatedAt"))
            if local_upd and remote_upd and local_upd > remote_upd:
                continue
        p.slug = slug or p.slug
        p.description = str(row.get("description") or row.get("desc") or p.description or "")
        p.category = str(row.get("category") or p.category or "")
        try:
            p.price = float(row.get("price") or row.get("amount") or p.price or 0)
        except Exception:
            pass
        p.image_url = str(row.get("image_url") or row.get("image") or p.image_url or "")
        p.external_url = str(row.get("external_url") or row.get("url") or p.external_url or "")
        changed += 1
    return changed


async def _sync_orders(db: AsyncSession, tenant_id: int, records: list[dict], cfg: dict | None = None) -> int:
    changed = 0
    for row in records:
        order_no = str(row.get("order_number") or row.get("orderNo") or row.get("code") or "").strip()
        if not order_no:
            continue
        result = await db.execute(select(Order).where(Order.tenant_id == tenant_id, Order.order_number == order_no))
        o = result.scalar_one_or_none()
        if not o:
            o = Order(tenant_id=tenant_id, order_number=order_no)
            db.add(o)
        elif cfg and (cfg.get("conflict_strategy") or "").strip().lower() == "manual":
            local_upd = o.updated_at
            remote_upd = _to_dt(row.get("updated_at") or row.get("updatedAt"))
            if local_upd and remote_upd and local_upd > remote_upd:
                continue
        o.customer_name = str(row.get("customer_name") or row.get("name") or o.customer_name or "")
        o.customer_phone = str(row.get("customer_phone") or row.get("phone") or o.customer_phone or "")
        o.customer_address = str(row.get("customer_address") or row.get("address") or o.customer_address or "")
        o.status = str(row.get("status") or o.status or "pending")
        try:
            o.total_amount = float(row.get("total_amount") or row.get("total") or o.total_amount or 0)
        except Exception:
            pass
        items = row.get("items")
        if isinstance(items, (list, dict)):
            o.items = json.dumps(items, ensure_ascii=False)
        o.cargo_tracking_no = str(row.get("cargo_tracking_no") or row.get("tracking_no") or o.cargo_tracking_no or "")
        o.cargo_company = str(row.get("cargo_company") or row.get("company") or o.cargo_company or "")
        changed += 1
    return changed


async def _sync_appointments(db: AsyncSession, tenant_id: int, records: list[dict]) -> int:
    changed = 0
    for row in records:
        when = _to_dt(row.get("scheduled_at") or row.get("appointment_at") or row.get("date"))
        if not when:
            continue
        phone = str(row.get("customer_phone") or row.get("phone") or "").strip()
        result = await db.execute(
            select(Appointment).where(
                Appointment.tenant_id == tenant_id,
                Appointment.scheduled_at == when,
                Appointment.customer_phone == phone,
            )
        )
        a = result.scalar_one_or_none()
        if not a:
            a = Appointment(tenant_id=tenant_id, scheduled_at=when)
            db.add(a)
        a.customer_name = str(row.get("customer_name") or row.get("name") or a.customer_name or "")
        a.customer_phone = phone or a.customer_phone
        a.service_type = str(row.get("service_type") or a.service_type or "")
        a.note = str(row.get("note") or a.note or "")
        a.status = str(row.get("status") or a.status or "pending")
        changed += 1
    return changed


async def _sync_reminders(db: AsyncSession, tenant_id: int, records: list[dict]) -> int:
    changed = 0
    for row in records:
        due = _to_dt(row.get("due_at") or row.get("remind_at") or row.get("date"))
        if not due:
            continue
        phone = str(row.get("customer_phone") or row.get("phone") or "").strip()
        result = await db.execute(
            select(Reminder).where(
                Reminder.tenant_id == tenant_id,
                Reminder.due_at == due,
                Reminder.customer_phone == phone,
            )
        )
        r = result.scalar_one_or_none()
        if not r:
            r = Reminder(tenant_id=tenant_id, due_at=due)
            db.add(r)
        r.customer_name = str(row.get("customer_name") or row.get("name") or r.customer_name or "")
        r.customer_phone = phone or r.customer_phone
        r.note = str(row.get("note") or r.note or "")
        r.status = str(row.get("status") or r.status or "pending")
        changed += 1
    return changed


async def _sync_admin_staff(db: AsyncSession, tenant_id: int, payload: Any, cfg: dict) -> int:
    changed = 0
    leave_rows = _normalize_records(payload, (cfg.get("leave_requests_path") or "").strip() or "leave_requests")
    inv_rows = _normalize_records(payload, (cfg.get("invoices_path") or "").strip() or "invoices")
    po_rows = _normalize_records(payload, (cfg.get("purchase_orders_path") or "").strip() or "purchase_orders")

    for row in leave_rows:
        name = str(row.get("employee_name") or row.get("name") or "").strip()
        start = _to_dt(str(row.get("start_date") or "") + " 00:00")
        end = _to_dt(str(row.get("end_date") or "") + " 00:00")
        if not (name and start and end):
            continue
        result = await db.execute(
            select(LeaveRequest).where(
                LeaveRequest.tenant_id == tenant_id,
                LeaveRequest.employee_name == name,
                LeaveRequest.start_date == start.date(),
                LeaveRequest.end_date == end.date(),
            )
        )
        lr = result.scalar_one_or_none()
        if not lr:
            lr = LeaveRequest(tenant_id=tenant_id, employee_name=name, start_date=start.date(), end_date=end.date())
            db.add(lr)
        lr.employee_phone = str(row.get("employee_phone") or row.get("phone") or lr.employee_phone or "")
        lr.leave_type = str(row.get("leave_type") or lr.leave_type or "")
        lr.note = str(row.get("note") or lr.note or "")
        lr.status = str(row.get("status") or lr.status or "pending")
        changed += 1

    for row in inv_rows:
        supplier = str(row.get("supplier_name") or row.get("supplier") or "").strip()
        if not supplier:
            continue
        inv_no = str(row.get("invoice_number") or row.get("number") or "").strip() or None
        result = None
        if inv_no:
            result = await db.execute(
                select(Invoice).where(Invoice.tenant_id == tenant_id, Invoice.invoice_number == inv_no)
            )
        inv = result.scalar_one_or_none() if result else None
        if not inv:
            inv = Invoice(tenant_id=tenant_id, supplier_name=supplier)
            db.add(inv)
        inv.supplier_name = supplier
        inv.invoice_number = inv_no or inv.invoice_number
        try:
            inv.total_amount = Decimal(str(row.get("total_amount") or row.get("total") or inv.total_amount or "0"))
        except Exception:
            pass
        inv.status = str(row.get("status") or inv.status or "pending")
        inv.note = str(row.get("note") or inv.note or "")
        changed += 1

    for row in po_rows:
        requester = str(row.get("requester_name") or row.get("requester") or "").strip()
        if not requester:
            continue
        supplier = str(row.get("supplier_name") or row.get("supplier") or "").strip() or None
        items = row.get("items") or row.get("items_json") or []
        if isinstance(items, str):
            try:
                parsed = json.loads(items)
                items = parsed if isinstance(parsed, list) else [{"name": str(items)}]
            except Exception:
                items = [{"name": str(items)}]
        if not isinstance(items, list):
            items = []
        items_json = json.dumps(items, ensure_ascii=False)
        result = await db.execute(
            select(PurchaseOrder).where(
                PurchaseOrder.tenant_id == tenant_id,
                PurchaseOrder.requester_name == requester,
                PurchaseOrder.items_json == items_json,
            )
        )
        po = result.scalar_one_or_none()
        if not po:
            po = PurchaseOrder(tenant_id=tenant_id, requester_name=requester, items_json=items_json)
            db.add(po)
        po.supplier_name = supplier or po.supplier_name
        po.note = str(row.get("note") or po.note or "")
        po.status = str(row.get("status") or po.status or "pending")
        changed += 1

    return changed


async def sync_module_pull(db: AsyncSession, tenant_id: int, module_id: str) -> dict:
    """
    Modul icin dis API'den veri cek ve local DB'ye yaz.
    Returns: {"ok": bool, "module": str, "count": int, "error": str|None}
    """
    started = perf_counter()
    ok = False
    try:
        cfg = await get_module_api_settings(tenant_id, module_id)
        if not cfg:
            return {"ok": False, "module": module_id, "count": 0, "error": "Modul API ayarlari bulunamadi"}
        if module_id == "admin_staff":
            payload = await _fetch_admin_staff_payload(cfg)
            count = await _sync_admin_staff(db, tenant_id, payload, cfg)
            await db.commit()
            ok = True
            return {"ok": True, "module": module_id, "count": count, "error": None}

        records = await _fetch_remote_records(module_id, cfg)
        mapping = _parse_field_mapping(cfg)
        reverse_mapping = _reverse_mapping(mapping)
        if reverse_mapping and module_id in {"contacts", "products", "orders"}:
            records = [_apply_reverse_mapping(r, reverse_mapping) for r in records if isinstance(r, dict)]
        if module_id == "contacts":
            count = await _sync_contacts(db, tenant_id, records, cfg=cfg)
        elif module_id == "products":
            count = await _sync_products(db, tenant_id, records, cfg=cfg)
        elif module_id == "orders":
            count = await _sync_orders(db, tenant_id, records, cfg=cfg)
        elif module_id == "appointments":
            count = await _sync_appointments(db, tenant_id, records)
        elif module_id == "reminders":
            count = await _sync_reminders(db, tenant_id, records)
        else:
            return {"ok": False, "module": module_id, "count": 0, "error": "Bu modul icin pull desteklenmiyor"}
        await db.commit()
        ok = True
        return {"ok": True, "module": module_id, "count": count, "error": None}
    except Exception as e:
        await db.rollback()
        return {"ok": False, "module": module_id, "count": 0, "error": str(e)[:300]}
    finally:
        duration_ms = int((perf_counter() - started) * 1000)
        record_trace_event(
            "external_sync",
            ok=ok,
            duration_ms=duration_ms,
            tenant_id=tenant_id,
            meta={"action": "pull", "module": module_id},
        )
        check_trace_alarm("external_sync")


async def preview_module_pull(db: AsyncSession, tenant_id: int, module_id: str) -> dict:
    """
    Modul icin dis API'den preview verisi getirir, DB'ye yazmaz.
    Returns: {"ok": bool, "module": str, "count": int, "sample": list[dict], "error": str|None}
    """
    cfg = await get_module_api_settings(tenant_id, module_id)
    if not cfg:
        return {"ok": False, "module": module_id, "count": 0, "sample": [], "error": "Modul API ayarlari bulunamadi"}
    try:
        if module_id == "admin_staff":
            payload = await _fetch_admin_staff_payload(cfg)
            leave_rows = _normalize_records(payload, (cfg.get("leave_requests_path") or "").strip() or "leave_requests")
            inv_rows = _normalize_records(payload, (cfg.get("invoices_path") or "").strip() or "invoices")
            po_rows = _normalize_records(payload, (cfg.get("purchase_orders_path") or "").strip() or "purchase_orders")
            all_rows = leave_rows + inv_rows + po_rows
            sample = [_preview_record(x) for x in all_rows[:3]]
            return {"ok": True, "module": module_id, "count": len(all_rows), "sample": sample, "error": None}

        records = await _fetch_remote_records(module_id, cfg)
        sample = [_preview_record(x) for x in records[:3]]
        return {"ok": True, "module": module_id, "count": len(records), "sample": sample, "error": None}
    except Exception as e:
        return {"ok": False, "module": module_id, "count": 0, "sample": [], "error": str(e)[:300]}


async def _local_records_for_push(db: AsyncSession, tenant_id: int, module_id: str) -> list[dict[str, Any]]:
    if module_id == "contacts":
        res = await db.execute(select(Contact).where(Contact.tenant_id == tenant_id).order_by(Contact.updated_at.desc()).limit(1000))
        rows = []
        for c in res.scalars().all():
            rows.append(
                {
                    "id": c.id,
                    "name": c.name or "",
                    "phone": c.phone or "",
                    "email": c.email or "",
                    "notes": c.notes or "",
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                }
            )
        return rows
    if module_id == "products":
        res = await db.execute(select(Product).where(Product.tenant_id == tenant_id).order_by(Product.updated_at.desc()).limit(1000))
        rows = []
        for p in res.scalars().all():
            rows.append(
                {
                    "id": p.id,
                    "name": p.name or "",
                    "slug": p.slug or "",
                    "description": p.description or "",
                    "category": p.category or "",
                    "price": p.price or 0,
                    "image_url": p.image_url or "",
                    "external_url": p.external_url or "",
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                }
            )
        return rows
    if module_id == "orders":
        res = await db.execute(select(Order).where(Order.tenant_id == tenant_id).order_by(Order.updated_at.desc()).limit(1000))
        rows = []
        for o in res.scalars().all():
            rows.append(
                {
                    "id": o.id,
                    "order_number": o.order_number or "",
                    "customer_name": o.customer_name or "",
                    "customer_phone": o.customer_phone or "",
                    "customer_address": o.customer_address or "",
                    "payment_option": o.payment_option or "",
                    "items": json.loads(o.items) if (o.items and str(o.items).strip().startswith("[")) else (o.items or ""),
                    "total_amount": o.total_amount or 0,
                    "status": o.status or "pending",
                    "cargo_tracking_no": o.cargo_tracking_no or "",
                    "cargo_company": o.cargo_company or "",
                    "updated_at": o.updated_at.isoformat() if o.updated_at else None,
                }
            )
        return rows
    return []


async def sync_module_push(db: AsyncSession, tenant_id: int, module_id: str) -> dict:
    """
    Modul icin local DB verisini dis API'ye push eder.
    Returns: {"ok": bool, "module": str, "count": int, "conflicts": int, "error": str|None}
    """
    started = perf_counter()
    ok = False
    pushed = 0
    conflicts = 0
    try:
        if module_id not in {"contacts", "products", "orders"}:
            return {"ok": False, "module": module_id, "count": 0, "conflicts": 0, "error": "Bu modul icin push desteklenmiyor"}
        cfg = await get_module_api_settings(tenant_id, module_id)
        if not cfg:
            return {"ok": False, "module": module_id, "count": 0, "conflicts": 0, "error": "Modul API ayarlari bulunamadi"}

        push_url = _get_push_url(cfg, module_id)
        if not push_url:
            return {"ok": False, "module": module_id, "count": 0, "conflicts": 0, "error": "Push API URL bos"}

        method = (cfg.get("push_method") or "POST").strip().upper()
        if method not in {"POST", "PUT", "PATCH"}:
            method = "POST"
        remote_id_field = (cfg.get("push_id_field") or ("phone" if module_id == "contacts" else ("slug" if module_id == "products" else "order_number"))).strip()
        mapping = _parse_field_mapping(cfg)
        local_id_field = _resolve_local_id_field(mapping, remote_id_field, remote_id_field)
        headers = _push_headers(cfg, module_id)
        local_rows = await _local_records_for_push(db, tenant_id, module_id)

        remote_index: dict[str, dict] = {}
        if (cfg.get("conflict_strategy") or "").strip().lower() == "manual":
            try:
                remote_rows = await _fetch_remote_records(module_id, cfg)
                for rr in remote_rows:
                    if not isinstance(rr, dict):
                        continue
                    key = _id_value(rr, remote_id_field)
                    if key:
                        remote_index[key] = rr
            except Exception:
                remote_index = {}

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            for local_row in local_rows:
                if _conflict_should_skip(cfg, local_row, remote_index, local_id_field):
                    conflicts += 1
                    continue
                payload = _apply_field_mapping(local_row, mapping)
                target_url = push_url
                if method in {"PUT", "PATCH"}:
                    pid = _id_value(payload, remote_id_field)
                    if pid:
                        target_url = f"{push_url.rstrip('/')}/{pid}"
                resp = await client.request(method, target_url, headers=headers, json=payload)
                if resp.status_code >= 400:
                    return {
                        "ok": False,
                        "module": module_id,
                        "count": pushed,
                        "conflicts": conflicts,
                        "error": f"Push HTTP {resp.status_code}: {(resp.text or '')[:200]}",
                    }
                pushed += 1
        ok = True
        return {"ok": True, "module": module_id, "count": pushed, "conflicts": conflicts, "error": None}
    except Exception as e:
        return {"ok": False, "module": module_id, "count": pushed, "conflicts": conflicts, "error": str(e)[:300]}
    finally:
        duration_ms = int((perf_counter() - started) * 1000)
        record_trace_event(
            "external_sync",
            ok=ok,
            duration_ms=duration_ms,
            tenant_id=tenant_id,
            meta={"action": "push", "module": module_id},
        )
        check_trace_alarm("external_sync")
