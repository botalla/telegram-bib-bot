"""Tests unitaires pour la vérification d'autorisation et de liste blanche."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Update, User

from src.bot.handlers import BotHandlers
from src.config import Settings


def test_is_user_allowed_strict():
    """Vérifie que la liste blanche est stricte et bloque tout par défaut."""
    # 1. Avec des utilisateurs autorisés
    settings = Settings(allowed_user_ids="12345,67890")
    assert settings.is_user_allowed(12345) is True
    assert settings.is_user_allowed(67890) is True
    assert settings.is_user_allowed(99999) is False
    assert settings.is_user_allowed(None) is False

    # 2. Sans utilisateur autorisé (fail-closed)
    empty_settings = Settings(allowed_user_ids="")
    assert empty_settings.is_user_allowed(12345) is False
    assert empty_settings.is_user_allowed(None) is False


@pytest.mark.asyncio
async def test_check_auth_decorator_blocks_unauthorized():
    """Vérifie que le décorateur @check_auth bloque immédiatement un utilisateur non autorisé."""
    handlers = BotHandlers()

    # Création d'un Update avec un utilisateur non autorisé
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = 99999  # ID non autorisé
    update.effective_user.username = "unknown_user"
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.callback_query = None

    context = MagicMock()

    # Exécution de n'importe quelle commande (ex: start_handler)
    await handlers.start_handler(update, context)

    # Doit avoir répondu le message d'accès refusé
    update.message.reply_text.assert_awaited_once()
    args, kwargs = update.message.reply_text.call_args
    assert "Accès refusé" in args[0]
