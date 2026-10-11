"""Gestionnaire de persistance de l'historique conversationnel multi-turn.

Conserve les échanges récents par utilisateur Telegram sur Google Cloud Storage (GCS)
ou en cache local (développement), permettant à l'agent IA Gemini de maintenir le contexte
au fil de la conversation.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)


class ConversationStore:
    """Stockage résilient de l'historique des conversations Telegram (GCS / Local)."""

    def __init__(
        self,
        settings: Settings | None = None,
        bucket_name: str | None = None,
        local_dir: str = ".conversation_cache",
    ):
        self.settings = settings or get_settings()
        self.bucket_name = bucket_name or self.settings.gcs_bucket_name
        self.local_dir = Path(local_dir)

        self._gcs_client = None
        self._gcs_available = False

        if self.bucket_name:
            try:
                from google.cloud import storage

                self._gcs_client = storage.Client()
                self._gcs_available = True
                logger.info(f"GCS ConversationStore activé sur le bucket : {self.bucket_name}")
            except Exception as e:
                logger.warning(
                    f"Impossible d'initialiser le client GCS pour ConversationStore ({e}). "
                    f"Repli sur le stockage local : {self.local_dir}"
                )
                self._gcs_available = False

    def _blob_name(self, user_id: int) -> str:
        """Nom du blob GCS pour un utilisateur donné."""
        return f"conversations/{user_id}.json"

    def _local_file_path(self, user_id: int) -> Path:
        """Chemin du fichier JSON local pour un utilisateur donné."""
        return self.local_dir / f"{user_id}.json"

    def _read_raw_data(self, user_id: int) -> dict[str, Any] | None:
        """Lit les données brutes de conversation depuis GCS ou le cache local."""
        # 1. Tentative GCS
        if self._gcs_available and self._gcs_client and self.bucket_name:
            try:
                bucket = self._gcs_client.bucket(self.bucket_name)
                blob = bucket.blob(self._blob_name(user_id))
                if blob.exists():
                    raw_text = blob.download_as_text()
                    return json.loads(raw_text)
            except Exception as e:
                logger.warning(f"Erreur lecture GCS conversation ({user_id}) : {e}. Tentative locale...")

        # 2. Repli local
        local_file = self._local_file_path(user_id)
        if local_file.exists():
            try:
                raw_text = local_file.read_text(encoding="utf-8")
                return json.loads(raw_text)
            except Exception as e:
                logger.warning(f"Erreur lecture fichier local conversation ({user_id}) : {e}")

        return None

    def _write_raw_data(self, user_id: int, data: dict[str, Any]) -> bool:
        """Écrit les données de conversation sur GCS et en local."""
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        saved = False

        # 1. GCS
        if self._gcs_available and self._gcs_client and self.bucket_name:
            try:
                bucket = self._gcs_client.bucket(self.bucket_name)
                blob = bucket.blob(self._blob_name(user_id))
                blob.upload_from_string(payload, content_type="application/json")
                saved = True
            except Exception as e:
                logger.warning(f"Erreur écriture GCS conversation ({user_id}) : {e}")

        # 2. Local
        try:
            if not self.local_dir.exists():
                self.local_dir.mkdir(parents=True, exist_ok=True)
            local_file = self._local_file_path(user_id)
            local_file.write_text(payload, encoding="utf-8")
            saved = True
        except Exception as e:
            logger.warning(f"Erreur écriture fichier local conversation ({user_id}) : {e}")

        return saved

    def get_recent_history(
        self,
        user_id: int,
        max_hours: float = 4.0,
        max_messages: int = 14,
    ) -> list[dict[str, str]]:
        """Récupère l'historique récent formaté pour Gemini.

        Applique :
        1. Le filtre temporel (< max_hours).
        2. Le plafonnement à max_messages.
        3. L'alternance stricte des rôles (user / model).
        4. Démarre toujours par un message 'user'.

        Returns:
            Liste de dictionnaires [{"role": "user"|"model", "text": "..."}]
        """
        raw_data = self._read_raw_data(user_id)
        if not raw_data or "messages" not in raw_data:
            return []

        messages: list[dict[str, Any]] = raw_data.get("messages", [])
        if not messages:
            return []

        now_ts = datetime.now(UTC).timestamp()
        cutoff_ts = now_ts - (max_hours * 3600)

        # 1. Filtrer par timestamp
        valid_messages = [
            m for m in messages
            if m.get("timestamp", 0) >= cutoff_ts and m.get("text") and m.get("role") in ("user", "model")
        ]

        if not valid_messages:
            return []

        # 2. Limiter au max_messages les plus récents
        if len(valid_messages) > max_messages:
            valid_messages = valid_messages[-max_messages:]

        # 3. Assurer que le premier message est un message 'user'
        while valid_messages and valid_messages[0]["role"] != "user":
            valid_messages.pop(0)

        if not valid_messages:
            return []

        # 4. Assurer l'alternance stricte en fusionnant les doublons de rôles consécutifs
        normalized: list[dict[str, str]] = []
        for msg in valid_messages:
            role = msg["role"]
            text = msg["text"].strip()
            if not text:
                continue

            if normalized and normalized[-1]["role"] == role:
                # Concaténer si deux tours consécutifs ont le même rôle
                normalized[-1]["text"] += f"\n{text}"
            else:
                normalized.append({"role": role, "text": text})

        return normalized

    def add_turn(
        self,
        user_id: int,
        user_text: str,
        model_text: str,
        retention_hours: float = 24.0,
        max_stored_messages: int = 50,
    ) -> bool:
        """Enregistre un aller-retour (tour utilisateur + réponse assistant) avec élagage."""
        now = datetime.now(UTC)
        now_ts = now.timestamp()

        raw_data = self._read_raw_data(user_id) or {
            "telegram_id": user_id,
            "created_at": now.isoformat(),
            "messages": [],
        }

        messages: list[dict[str, Any]] = raw_data.get("messages", [])

        # Ajout du tour
        messages.append({
            "role": "user",
            "text": user_text.strip(),
            "timestamp": now_ts,
        })
        messages.append({
            "role": "model",
            "text": model_text.strip(),
            "timestamp": now_ts,
        })

        # Élagage des vieux messages (> retention_hours)
        cutoff_ts = now_ts - (retention_hours * 3600)
        messages = [m for m in messages if m.get("timestamp", 0) >= cutoff_ts]

        # Plafonnement absolu de taille du fichier
        if len(messages) > max_stored_messages:
            messages = messages[-max_stored_messages:]

        raw_data["updated_at"] = now.isoformat()
        raw_data["messages"] = messages

        return self._write_raw_data(user_id, raw_data)

    def clear_history(self, user_id: int) -> bool:
        """Réinitialise l'historique conversationnel d'un utilisateur."""
        success = True

        # GCS
        if self._gcs_available and self._gcs_client and self.bucket_name:
            try:
                bucket = self._gcs_client.bucket(self.bucket_name)
                blob = bucket.blob(self._blob_name(user_id))
                if blob.exists():
                    blob.delete()
                    logger.info(f"Historique GCS supprimé pour user_id={user_id}")
            except Exception as e:
                logger.warning(f"Erreur suppression GCS conversation ({user_id}) : {e}")
                success = False

        # Local
        local_file = self._local_file_path(user_id)
        if local_file.exists():
            try:
                local_file.unlink()
                logger.info(f"Historique local supprimé pour user_id={user_id}")
            except Exception as e:
                logger.warning(f"Erreur suppression fichier local conversation ({user_id}) : {e}")
                success = False

        return success
