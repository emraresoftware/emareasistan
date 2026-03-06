"""Kurum bazlı iş akışları - Workflow Builder"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from datetime import datetime

from .database import Base


class TenantWorkflow(Base):
    """
    Kurum bazlı iş akışı.
    Platform: whatsapp, telegram, instagram
    """
    __tablename__ = "tenant_workflows"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False, default=1)
    platform = Column(String(50), nullable=False)  # whatsapp, telegram, instagram
    workflow_name = Column(String(255), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    graph_layout = Column(Text)  # JSON: {nodes:[{id,step_id,x,y}], edges:[{source,target}]} - Drawflow
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkflowStep(Base):
    """
    İş akışı adımı.
    step_type: trigger, action, condition
    config: JSON - adıma özel ayarlar
    """
    __tablename__ = "workflow_steps"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("tenant_workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    step_name = Column(String(255), nullable=False)
    step_type = Column(String(30), nullable=False)  # trigger, action, condition
    config = Column(Text)  # JSON: {"key": "value"}
    order_index = Column(Integer, default=0)  # Sıra
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProcessConfig(Base):
    """
    Kurum bazlı süreç konfigürasyonu.
    process_type: order_management, customer_service, marketing
    """
    __tablename__ = "process_configs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False, default=1)
    process_type = Column(String(50), nullable=False)  # order_management, customer_service, marketing
    platform = Column(String(50), nullable=False)  # whatsapp, telegram, instagram
    auto_response = Column(Boolean, default=True)
    escalation_rules = Column(Text)  # JSON: {"after_seconds": 300, "assign_to": "agent"}
    sla_settings = Column(Text)  # JSON: {"response_time_seconds": 60, "resolution_hours": 24}
    notification_rules = Column(Text)  # JSON: [{"event": "new_order", "channels": ["whatsapp"]}]
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
