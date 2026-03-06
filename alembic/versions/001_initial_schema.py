"""initial_schema - Tüm tabloları oluştur

Revision ID: 001
Revises:
Create Date: 2026-02-13

PostgreSQL ve SQLite uyumlu. Mevcut SQLite DB için: alembic stamp 001
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # tenants
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=True),
        sa.Column("website_url", sa.String(512), nullable=False),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("settings", sa.Text(), nullable=True),
        sa.Column("products_path", sa.String(512), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("enabled_modules", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    # whatsapp_connections
    op.create_table(
        "whatsapp_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("auth_path", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("phone_number", sa.String(30), nullable=True),
        sa.Column("bridge_port", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_whatsapp_connections_tenant_id", "whatsapp_connections", ["tenant_id"])
    op.create_index("ix_whatsapp_connections_auth_path", "whatsapp_connections", ["auth_path"], unique=True)

    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("role", sa.String(20), nullable=True),
        sa.Column("whatsapp_connection_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["whatsapp_connection_id"], ["whatsapp_connections.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    # contacts
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contacts_phone", "contacts", ["phone"])
    op.create_index("ix_contacts_tenant_id", "contacts", ["tenant_id"])

    # conversations
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("platform", sa.String(20), nullable=True),
        sa.Column("platform_user_id", sa.String(100), nullable=True),
        sa.Column("customer_name", sa.String(255), nullable=True),
        sa.Column("customer_phone", sa.String(20), nullable=True),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("agent_taken_over_at", sa.DateTime(), nullable=True),
        sa.Column("agent_name", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("order_draft", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversations_platform_user_id", "conversations", ["platform_user_id"])
    op.create_index("ix_conversations_tenant_id", "conversations", ["tenant_id"])

    # messages
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(20), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("extra_data", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    # orders
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("order_number", sa.String(50), nullable=True),
        sa.Column("customer_name", sa.String(255), nullable=True),
        sa.Column("customer_phone", sa.String(20), nullable=True),
        sa.Column("customer_address", sa.Text(), nullable=True),
        sa.Column("payment_option", sa.String(50), nullable=True),
        sa.Column("items", sa.Text(), nullable=True),
        sa.Column("total_amount", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("cargo_tracking_no", sa.String(100), nullable=True),
        sa.Column("cargo_company", sa.String(50), nullable=True),
        sa.Column("platform", sa.String(20), nullable=True),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orders_order_number", "orders", ["order_number"], unique=True)
    op.create_index("ix_orders_tenant_id", "orders", ["tenant_id"])

    # response_rules
    op.create_table(
        "response_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("trigger_type", sa.String(20), nullable=True),
        sa.Column("trigger_value", sa.String(200), nullable=True),
        sa.Column("product_ids", sa.Text(), nullable=True),
        sa.Column("image_urls", sa.Text(), nullable=True),
        sa.Column("custom_message", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_response_rules_tenant_id", "response_rules", ["tenant_id"])

    # image_albums
    op.create_table(
        "image_albums",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(150), nullable=True),
        sa.Column("image_urls", sa.Text(), nullable=True),
        sa.Column("vehicle_models", sa.Text(), nullable=True),
        sa.Column("custom_message", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_image_albums_tenant_id", "image_albums", ["tenant_id"])

    # videos
    op.create_table(
        "videos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(150), nullable=True),
        sa.Column("trigger_keyword", sa.String(100), nullable=True),
        sa.Column("vehicle_models", sa.Text(), nullable=True),
        sa.Column("video_url", sa.Text(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_videos_tenant_id", "videos", ["tenant_id"])

    # reminders
    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("contact_id", sa.Integer(), nullable=True),
        sa.Column("customer_name", sa.String(255), nullable=True),
        sa.Column("customer_phone", sa.String(20), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reminders_tenant_id", "reminders", ["tenant_id"])

    # products
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("image_url", sa.String(512), nullable=True),
        sa.Column("image_urls", sa.Text(), nullable=True),
        sa.Column("vehicle_compatibility", sa.Text(), nullable=True),
        sa.Column("stock_status", sa.String(20), nullable=True),
        sa.Column("external_url", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_products_category", "products", ["category"])
    op.create_index("ix_products_slug", "products", ["slug"], unique=True)

    # ai_training_examples
    op.create_table(
        "ai_training_examples",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_training_examples_tenant_id", "ai_training_examples", ["tenant_id"])

    # pending_registrations
    op.create_table(
        "pending_registrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(64), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("website_url", sa.String(512), nullable=False),
        sa.Column("tenant_name", sa.String(255), nullable=True),
        sa.Column("tenant_slug", sa.String(100), nullable=True),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("products_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pending_registrations_token", "pending_registrations", ["token"], unique=True)


def downgrade() -> None:
    op.drop_table("pending_registrations")
    op.drop_table("ai_training_examples")
    op.drop_table("products")
    op.drop_table("reminders")
    op.drop_table("videos")
    op.drop_table("image_albums")
    op.drop_table("response_rules")
    op.drop_table("orders")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("contacts")
    op.drop_table("users")
    op.drop_table("whatsapp_connections")
    op.drop_table("tenants")
