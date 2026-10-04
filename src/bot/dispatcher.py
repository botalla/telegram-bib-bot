"""Configuration du routeur d'événements Telegram.

Initialise l'application python-telegram-bot et enregistre l'ensemble des
gestionnaires de commandes, de boutons interactifs et de messages.
"""

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.bot.handlers import BotHandlers
from src.config import Settings, get_settings

logger = logging.getLogger(__name__)


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Capture et journalise toute exception non gérée dans le bot Telegram."""
    logger.exception("Exception non interceptée lors du traitement d'un update Telegram :", exc_info=context.error)

    if isinstance(update, Update) and update.effective_chat:
        user_message = "⚠️ Une erreur inattendue est survenue. Veuillez réessayer dans un instant."
        err_str = str(context.error or "")

        # Si l'erreur est liée au portail de la ville de Paris ou au réseau
        if isinstance(context.error, ConnectionError) or "ConnectError" in type(context.error).__name__ or "ConnectError" in err_str:
            user_message = (
                "🏛️ <b>Portail indisponible</b>\n\n"
                "Le site des Bibliothèques de la Ville de Paris est temporairement inaccessible ou ne répond pas. "
                "Veuillez réessayer dans quelques instants."
            )

        try:
            from telegram.constants import ParseMode
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=user_message,
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.warning(f"Impossible d'envoyer la notification d'erreur à l'utilisateur : {e}")


def build_application(settings: Settings | None = None) -> Application:
    """Construit et configure l'instance Application de python-telegram-bot."""
    settings = settings or get_settings()

    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN non renseigné. L'application bot ne pourra pas se connecter.")

    # Construction de l'application
    app = Application.builder().token(settings.telegram_bot_token or "123456:DUMMY").build()

    # Enregistrement du gestionnaire d'erreur global
    app.add_error_handler(global_error_handler)

    # Gestionnaires métier (chacun protégé par le décorateur @check_auth)
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
