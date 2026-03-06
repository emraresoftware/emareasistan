"""Veritabanı bağlantısı ve oturum yönetimi"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy deklaratif taban sınıfı. Tüm modeller bu sınıftan türer."""
    pass


engine = create_async_engine(
    get_settings().database_url,
    echo=False,
)
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db():
    """Dependency for FastAPI - DB session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Tabloları oluştur"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # PostgreSQL extensions (opsiyonel)
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:
            pass
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        except Exception:
            pass
        # Migration: payment_option sütunu (mevcut orders tablosu için)
        def _add_payment_column(sync_conn):
            try:
                sync_conn.execute(text("SELECT payment_option FROM orders LIMIT 1"))
            except Exception:
                try:
                    sync_conn.execute(text("ALTER TABLE orders ADD COLUMN payment_option VARCHAR(50)"))
                except Exception:
                    pass
        try:
            await conn.run_sync(_add_payment_column)
        except Exception:
            pass
        # Migration: agent takeover sütunları
        def _add_agent_columns(sync_conn):
            try:
                sync_conn.execute(text("SELECT agent_taken_over_at FROM conversations LIMIT 1"))
            except Exception:
                try:
                    sync_conn.execute(text("ALTER TABLE conversations ADD COLUMN agent_taken_over_at VARCHAR"))
                except Exception:
                    pass
            try:
                sync_conn.execute(text("SELECT agent_name FROM conversations LIMIT 1"))
            except Exception:
                try:
                    sync_conn.execute(text("ALTER TABLE conversations ADD COLUMN agent_name VARCHAR(100)"))
                except Exception:
                    pass
            try:
                sync_conn.execute(text("SELECT notes FROM conversations LIMIT 1"))
            except Exception:
                try:
                    sync_conn.execute(text("ALTER TABLE conversations ADD COLUMN notes TEXT"))
                except Exception:
                    pass
        try:
            await conn.run_sync(_add_agent_columns)
        except Exception:
            pass
        # Migration: tenant_id sütunları (multi-tenant)
        def _add_tenant_columns(sync_conn):
            for table, col in [
                ("conversations", "tenant_id"),
                ("orders", "tenant_id"),
                ("response_rules", "tenant_id"),
                ("image_albums", "tenant_id"),
                ("contacts", "tenant_id"),
                ("whatsapp_connections", "tenant_id"),
                ("reminders", "tenant_id"),
                ("users", "tenant_id"),
            ]:
                try:
                    sync_conn.execute(text(f"SELECT {col} FROM {table} LIMIT 1"))
                except Exception:
                    try:
                        sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} INTEGER"))
                    except Exception:
                        pass
        try:
            await conn.run_sync(_add_tenant_columns)
        except Exception:
            pass
        # Mevcut NULL tenant_id'leri 1 yap
        def _backfill_tenant_id(sync_conn):
            for table in ["conversations", "orders", "response_rules", "image_albums", "contacts", "whatsapp_connections", "reminders", "users"]:
                try:
                    sync_conn.execute(text(f"UPDATE {table} SET tenant_id = 1 WHERE tenant_id IS NULL"))
                except Exception:
                    pass
        try:
            await conn.run_sync(_backfill_tenant_id)
        except Exception:
            pass
        # Migration: videos.vehicle_models ve priority (albüm gibi araç seçimi)
        def _add_video_vehicle_columns(sync_conn):
            for col, col_type in [("vehicle_models", "TEXT"), ("priority", "INTEGER")]:
                try:
                    sync_conn.execute(text(f"SELECT {col} FROM videos LIMIT 1"))
                except Exception:
                    try:
                        sync_conn.execute(text(f"ALTER TABLE videos ADD COLUMN {col} {col_type}"))
                    except Exception:
                        pass
        try:
            await conn.run_sync(_add_video_vehicle_columns)
        except Exception:
            pass
        # Migration: conversations.order_draft (sipariş state machine)
        def _add_order_draft(sync_conn):
            try:
                sync_conn.execute(text("SELECT order_draft FROM conversations LIMIT 1"))
            except Exception:
                try:
                    sync_conn.execute(text("ALTER TABLE conversations ADD COLUMN order_draft TEXT"))
                except Exception:
                    pass
        try:
            await conn.run_sync(_add_order_draft)
        except Exception:
            pass
        # Migration: audit_logs tablosu
        def _add_audit_logs(sync_conn):
            try:
                sync_conn.execute(text("SELECT id FROM audit_logs LIMIT 1"))
            except Exception:
                try:
                    sync_conn.execute(text("""
                        CREATE TABLE audit_logs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            tenant_id INTEGER,
                            user_id INTEGER,
                            user_email VARCHAR(255),
                            action VARCHAR(100) NOT NULL,
                            resource VARCHAR(100),
                            resource_id VARCHAR(50),
                            details TEXT,
                            ip_address VARCHAR(45),
                            created_at DATETIME
                        )
                    """))
                    sync_conn.execute(text("CREATE INDEX ix_audit_logs_tenant_id ON audit_logs(tenant_id)"))
                    sync_conn.execute(text("CREATE INDEX ix_audit_logs_created_at ON audit_logs(created_at)"))
                except Exception:
                    pass
        try:
            await conn.run_sync(_add_audit_logs)
        except Exception:
            pass
        # Migration: tenants.enabled_modules (modül sistemi)
        def _add_tenant_enabled_modules(sync_conn):
            try:
                sync_conn.execute(text("SELECT enabled_modules FROM tenants LIMIT 1"))
            except Exception:
                try:
                    sync_conn.execute(text("ALTER TABLE tenants ADD COLUMN enabled_modules TEXT"))
                except Exception:
                    pass
        try:
            await conn.run_sync(_add_tenant_enabled_modules)
        except Exception:
            pass
