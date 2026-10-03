"""Configuration centralisée de l'application BiblioBot Paris.

Ce module gère le chargement typé et validé des variables d'environnement
et des secrets injectés par GCP Secret Manager ou un fichier .env local.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres applicatifs avec validation Pydantic."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Identifiants Telegram
    telegram_bot_token: str = Field(
        default="",
        description="Jeton d'API Telegram Bot fourni par @BotFather",
    )
    telegram_webhook_secret: str = Field(
        default="",
        description="Jeton secret pour valider le header X-Telegram-Bot-Api-Secret-Token",
    )
    allowed_user_ids: str = Field(
        default="",
        description="Liste d'identifiants d'utilisateurs Telegram autorisés (séparés par virgule)",
    )

    # Configuration IA Gemini
    gemini_api_key: str = Field(
        default="",
        description="Clé d'API Google Gemini",
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Modèle Gemini utilisé pour le Function Calling",
    )

    # Identifiants Portail Syracuse (Bibliothèques de Paris)
    parisbib_username: str = Field(
        default="",
        description="Numéro de carte ou identifiant principal Syracuse",
    )
    parisbib_password: str = Field(
        default="",
        description="Mot de passe ou code PIN du compte Syracuse",
    )

    # Persistance de Session
    gcs_bucket_name: str | None = Field(
        default=None,
        description="Nom du bucket Google Cloud Storage pour stocker les cookies de session",
    )
    local_session_file: str = Field(
        default=".session_cache.json",
        description="Chemin local du fichier de session en environnement de développement",
    )

    # Serveur HTTP FastAPI
    port: int = Field(default=8080, description="Port d'écoute du serveur ASGI")
    host: str = Field(default="0.0.0.0", description="Hôte d'écoute du serveur ASGI")
    log_level: str = Field(default="INFO", description="Niveau de journalisation (DEBUG, INFO, etc.)")
    environment: str = Field(default="production", description="Environnement (development, production)")

    @property
    def allowed_users_set(self) -> set[int]:
        """Retourne l'ensemble des IDs Telegram autorisés."""
        if not self.allowed_user_ids:
            return set()
        user_ids = set()
        for raw_id in self.allowed_user_ids.split(","):
            cleaned = raw_id.strip()
            if cleaned.isdigit():
                user_ids.add(int(cleaned))
        return user_ids

    def is_user_allowed(self, user_id: int | None) -> bool:
        """Vérifie si un ID Telegram est présent dans la liste blanche."""
        if user_id is None:
            return False
        allowed = self.allowed_users_set
        # Si aucune restriction n'est configurée (ex: dev local non restreint)
        if not allowed:
            return True
        return user_id in allowed


@lru_cache
def get_settings() -> Settings:
    """Fournit une instance singleton des paramètres applicatifs."""
    return Settings()
