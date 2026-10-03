"""Configuration du routeur d'événements et filtrage de sécurité Telegram.

Initialise l'application python-telegram-bot, configure les gestionnaires
et applique la liste blanche stricte des utilisateurs (whitelist).
"""

import logging
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from src.bot.handlers import BotHandlers
from src.config import Settings, get_settings

logger = logging.getLogger(__name__)


async def auth_filter_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Intercepteur de sécurité : vérifie si l'utilisateur Telegram est autorisé."""
    user = update.effective_user
    if not user:
        return

    settings = get_settings()
    if not settings.is_user_allowed(user.id):
        logger.warning(
            f"⛔ Accès rejeté pour l'utilisateur non autorisé ID={user.id} (@{user.username or 'N/A'})"
        )
        # Stoppe la propagation de l'événement
        from telegram.ext import ApplicationHandlerStop

        raise ApplicationHandlerStop()


def build_application(settings: Settings | None = None) -> Application:
    """Construit et configure l'instance Application de python-telegram-bot."""
    settings = settings or get_settings()

    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN non renseigné. L'application bot ne pourra pas se connecter.")

    # Construction de l'application
    app = Application.builder().token(settings.telegram_bot_token or "123456:DUMMY").build()

    # 1. Filtre d'authentification whitelist en priorité absolue (-1)
    app.add_handler(TypeHandler(Update, auth_filter_middleware), group=-1)

    # 2. Gestionnaires métier
    handlers = BotHandlers()

    app.add_handler(CommandHandler("start", handlers.start_handler))
    app.add_handler(CommandHandler("emprunts", handlers.emprunts_handler))
    app.add_handler(CommandHandler("urgences", handlers.urgences_handler))
    app.add_handler(CommandHandler("membre", handlers.membre_handler))
    app.add_handler(CommandHandler("prolonger", handlers.batch_renew_handler))
    app.add_handler(CommandHandler("couvertures", handlers.covers_handler))
    app.add_handler(CommandHandler("aide", handlers.help_handler))

    # Clics sur boutons interactifs
    app.add_handler(CallbackQueryHandler(handlers.callback_query_handler))

    # Messages texte libres en langage naturel
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.text_message_handler))

    return app
