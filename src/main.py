"""Point d'entrée principal FastAPI & serveur Webhook pour Google Cloud Run.

Expose l'écouteur HTTP asynchrone pour les updates Telegram avec vérification
du jeton de sécurité X-Telegram-Bot-Api-Secret-Token, et probe de santé /healthz.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from telegram import Update

from src.bot.dispatcher import build_application
from src.config import get_settings

# Configuration des logs
settings = get_settings()
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("biblio_bot_main")

# Instance globale de l'application python-telegram-bot
ptb_app = build_application(settings=settings)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gestionnaire de cycle de vie du serveur FastAPI et du bot Telegram."""
    logger.info("🚀 Démarrage du conteneur BiblioBot...")
    await ptb_app.initialize()
    await ptb_app.start()
    logger.info("✅ Application Telegram initialisée avec succès.")

    yield

    logger.info("🛑 Arrêt de l'application BiblioBot...")
    await ptb_app.stop()
    await ptb_app.shutdown()
    logger.info("👋 Application fermée proprement.")


app = FastAPI(
    title="BiblioBot Paris - Webhook Server",
    description="Serveur Webhook Telegram serverless pour les Bibliothèques de la Ville de Paris",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/healthz", status_code=status.HTTP_200_OK, tags=["Monitoring"])
async def health_check() -> dict:
    """Probe de santé pour Google Cloud Run et monitoring d'uptime."""
    return {
        "status": "healthy",
        "service": "biblio-bot",
        "environment": settings.environment,
    }


@app.post("/webhook", status_code=status.HTTP_200_OK, tags=["Telegram"])
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> Response:
    """Endpoint de réception des événements Telegram Webhook."""
    # 1. Vérification du jeton secret Webhook
    expected_secret = settings.telegram_webhook_secret
    if expected_secret and (
        not x_telegram_bot_api_secret_token or x_telegram_bot_api_secret_token != expected_secret
    ):
        logger.warning("⛔ Rejet Webhook : Secret token absent ou invalide.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Secret token mismatch",
        )

    # 2. Lecture et désérialisation de l'Update Telegram
    try:
        raw_body = await request.json()
    except Exception as e:
        logger.error(f"Erreur de lecture du JSON de la requête : {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from e

    # 3. Traitement asynchrone par python-telegram-bot
    try:
        update = Update.de_json(data=raw_body, bot=ptb_app.bot)
        if update:
            await ptb_app.process_update(update)
    except Exception as e:
        logger.exception(f"Erreur lors du traitement de l'update Telegram : {e}")

    # Telegram attend un statut HTTP 200 immédiat pour confirmer la bonne réception
    return Response(status_code=status.HTTP_200_OK)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
    )
