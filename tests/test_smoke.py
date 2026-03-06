"""
Smoke testler — uygulamanın temel bileşenlerinin çalıştığını doğrular.
Bu testler hiçbir harici servise bağımlı değildir.
"""
import pytest


class TestAppImport:
    """Uygulama import testleri."""

    def test_main_app_import(self):
        """main.py başarıyla import edilebilir."""
        from main import app
        assert app is not None

    def test_app_has_routes(self):
        """Uygulama yeterli sayıda route içerir."""
        from main import app
        assert len(app.routes) > 100

    def test_config_import(self):
        """Config modülü import edilebilir."""
        from config import get_settings
        settings = get_settings()
        assert settings is not None

    def test_models_import(self):
        """Tüm modeller import edilebilir."""
        from models import (
            Tenant, User, Conversation, Message,
            Product, Order, ResponseRule, AITrainingExample,
        )
        assert Tenant is not None
        assert User is not None

    def test_modules_import(self):
        """Modül sistemi import edilebilir."""
        from services.modules import AVAILABLE_MODULES
        assert len(AVAILABLE_MODULES) >= 50

    def test_chat_handler_import(self):
        """ChatHandler import edilebilir."""
        from integrations.chat_handler import ChatHandler
        assert ChatHandler is not None

    def test_channel_base_import(self):
        """Kanal base sınıfları import edilebilir."""
        from integrations.channels.base import BaseChannel, InboundMessage, ChatResponse
        assert BaseChannel is not None
        assert InboundMessage is not None
        assert ChatResponse is not None


class TestHealthEndpoint:
    """Health endpoint testleri."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, test_client):
        """Health endpoint 200 döner."""
        response = await test_client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_response_structure(self, test_client):
        """Health endpoint doğru yapıda yanıt döner."""
        response = await test_client.get("/health")
        data = response.json()
        assert "status" in data
        assert "uptime" in data


class TestRootRedirect:
    """Kök URL yönlendirme testi."""

    @pytest.mark.asyncio
    async def test_root_redirects_to_admin(self, test_client):
        """/ adresi /admin'e yönlendirir."""
        response = await test_client.get("/", follow_redirects=False)
        assert response.status_code in (301, 302, 307)
        assert "/admin" in response.headers.get("location", "")


class TestSecurityHeaders:
    """Güvenlik header'ları testleri."""

    @pytest.mark.asyncio
    async def test_xframe_options(self, test_client):
        """X-Frame-Options header'ı mevcut."""
        response = await test_client.get("/health")
        assert response.headers.get("x-frame-options") == "SAMEORIGIN"

    @pytest.mark.asyncio
    async def test_content_type_options(self, test_client):
        """X-Content-Type-Options header'ı mevcut."""
        response = await test_client.get("/health")
        assert response.headers.get("x-content-type-options") == "nosniff"

    @pytest.mark.asyncio
    async def test_xss_protection(self, test_client):
        """X-XSS-Protection header'ı mevcut."""
        response = await test_client.get("/health")
        assert "1" in response.headers.get("x-xss-protection", "")
