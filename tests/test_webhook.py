"""Tests unitaires pour le serveur FastAPI et l'endpoint Webhook."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_healthz_endpoint():
    """Vérifie que le point de santé /healthz répond HTTP 200."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "biblio-bot"


@pytest.mark.asyncio
async def test_webhook_rejects_missing_secret():
    """Vérifie le rejet HTTP 403 si le secret_token Telegram est absent ou incorrect."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Sans header
        with patch("src.main.settings.telegram_webhook_secret", "secret_requis_123"):
            response = await client.post("/webhook", json={"update_id": 1})
            assert response.status_code == 403

            # 2. Avec mauvais header
            response_bad = await client.post(
                "/webhook",
                json={"update_id": 1},
                headers={"X-Telegram-Bot-Api-Secret-Token": "mauvais_secret"},
            )
            assert response_bad.status_code == 403


@pytest.mark.asyncio
async def test_webhook_accepts_valid_secret():
    """Vérifie que la requête est acceptée (HTTP 200) avec le bon header."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with (
            patch("src.main.settings.telegram_webhook_secret", "secret_valide_456"),
            patch("src.main.ptb_app.process_update", new=AsyncMock()),
        ):
            response = await client.post(
                "/webhook",
                json={"update_id": 100, "message": {"text": "/start"}},
                headers={"X-Telegram-Bot-Api-Secret-Token": "secret_valide_456"},
            )
            assert response.status_code == 200
