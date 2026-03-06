"""audit_logs: user_agent ve success kolonları (giriş cihazı ve başarı durumu)

Revision ID: 023
Revises: 022
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("audit_logs", sa.Column("user_agent", sa.String(512), nullable=True))
    op.add_column("audit_logs", sa.Column("success", sa.Integer(), nullable=True, server_default="1"))


def downgrade():
    op.drop_column("audit_logs", "user_agent")
    op.drop_column("audit_logs", "success")
