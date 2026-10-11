"""Tests unitaires pour les handlers liés à l'historique conversationnel."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Message, Update, User

from src.bot.handlers import BotHandlers


@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = 12345678
    user.username = "testuser"
    update.effective_user = user

    chat = MagicMock()
    chat.id = 12345678
    update.effective_chat = chat

    message = MagicMock(spec=Message)
    message.text = "Bonjour !"
    message.reply_text = AsyncMock()
    update.message = message
    update.callback_query = None
    return update


@pytest.fixture
def mock_context():
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.bot.send_chat_action = AsyncMock()
    return context


@pytest.mark.asyncio
async def test_reset_handler(mock_update, mock_context, mock_settings, monkeypatch):
    """Vérifie que la commande /reset efface l'historique de l'utilisateur."""
    monkeypatch.setattr("src.bot.handlers.get_settings", lambda: mock_settings)
    mock_store = MagicMock()
    handlers = BotHandlers(conversation_store=mock_store)

    await handlers.reset_handler(mock_update, mock_context)

    mock_store.clear_history.assert_called_once_with(12345678)
    mock_update.message.reply_text.assert_called_once()
    args, _ = mock_update.message.reply_text.call_args
    assert "Mémoire réinitialisée" in args[0]


@pytest.mark.asyncio
async def test_text_message_handler_with_history(mock_update, mock_context, mock_settings, monkeypatch):
    """Vérifie que text_message_handler lit l'historique et persiste le nouvel échange."""
    monkeypatch.setattr("src.bot.handlers.get_settings", lambda: mock_settings)
    mock_store = MagicMock()
    mock_store.get_recent_history.return_value = [
        {"role": "user", "text": "Tour précédent user"},
        {"role": "model", "text": "Tour précédent bot"},
    ]

    mock_agent = MagicMock()
    mock_agent.chat = AsyncMock(return_value={"text": "Réponse générée par IA", "media_urls": []})

    handlers = BotHandlers(gemini_agent=mock_agent, conversation_store=mock_store)

    mock_update.message.text = "Ma question"

    await handlers.text_message_handler(mock_update, mock_context)

    # Vérification lecture historique
    mock_store.get_recent_history.assert_called_once_with(
        user_id=12345678,
        max_hours=4.0,
        max_messages=14,
    )

    # Vérification transmission à chat
    mock_agent.chat.assert_awaited_once_with(
        "Ma question",
        history=[
            {"role": "user", "text": "Tour précédent user"},
            {"role": "model", "text": "Tour précédent bot"},
        ],
    )

    # Vérification enregistrement du nouvel échange
    mock_store.add_turn.assert_called_once_with(
        user_id=12345678,
        user_text="Ma question",
        model_text="Réponse générée par IA",
    )
