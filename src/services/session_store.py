"""Gestionnaire de persistance des cookies de session Syracuse.

Ce service implémente le pattern 'Stateless Compute, Stateful Session' :
- Sur Google Cloud Run : Sauvegarde et lecture des cookies dans Google Cloud Storage (GCS).
- En développement local : Sauvegarde et lecture dans un fichier JSON local.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class SessionStore:
    """Stockage résilient des cookies de session Syracuse (GCS / Local)."""

    def __init__(self, bucket_name: Optional[str] = None, local_file_path: str = ".session_cache.json"):
        self.bucket_name = bucket_name
        self.local_file_path = Path(local_file_path)
        self._gcs_client = None
        self._gcs_available = False

        if self.bucket_name:
            try:
                from google.cloud import storage

                self._gcs_client = storage.Client()
                self._gcs_available = True
                logger.info(f"GCS SessionStore activé sur le bucket : {self.bucket_name}")
            except Exception as e:
                logger.warning(
                    f"Impossible d'initialiser le client GCS ({e}). Repli sur le stockage local : {self.local_file_path}"
                )
                self._gcs_available = False

    def load_session(self) -> Optional[Dict[str, str]]:
        """Charge les cookies de session depuis GCS ou le cache local."""
        # 1. Tentative via GCS
        if self._gcs_available and self._gcs_client and self.bucket_name:
            try:
                bucket = self._gcs_client.bucket(self.bucket_name)
                blob = bucket.blob("syracuse_session.json")
                if blob.exists():
                    raw_data = blob.download_as_text()
                    data = json.loads(raw_data)
                    logger.info("Cookies de session Syracuse chargés avec succès depuis GCS.")
                    return data
            except Exception as e:
                logger.warning(f"Erreur lors de la lecture de la session sur GCS ({e}). Tentative locale...")

        # 2. Repli local
        if self.local_file_path.exists():
            try:
                raw_data = self.local_file_path.read_text(encoding="utf-8")
                data = json.loads(raw_data)
                logger.info("Cookies de session Syracuse chargés depuis le cache local.")
                return data
            except Exception as e:
                logger.warning(f"Erreur lors de la lecture du fichier de session local : {e}")

        return None

    def save_session(self, cookies: Dict[str, str]) -> bool:
        """Sauvegarde les cookies de session sur GCS et/ou en local."""
        payload = json.dumps(cookies, ensure_ascii=False, indent=2)
        saved = False

        # 1. Sauvegarde sur GCS
        if self._gcs_available and self._gcs_client and self.bucket_name:
            try:
                bucket = self._gcs_client.bucket(self.bucket_name)
                blob = bucket.blob("syracuse_session.json")
                blob.upload_from_string(payload, content_type="application/json")
                logger.info("Cookies de session Syracuse persistés sur GCS.")
                saved = True
            except Exception as e:
                logger.warning(f"Échec de sauvegarde de session sur GCS : {e}")

        # 2. Sauvegarde en cache local
        try:
            self.local_file_path.write_text(payload, encoding="utf-8")
            saved = True
        except Exception as e:
            logger.warning(f"Échec de sauvegarde locale de la session : {e}")

        return saved

    def clear_session(self) -> None:
        """Supprime la session en cas d'invalidation explicite ou déconnexion."""
        if self._gcs_available and self._gcs_client and self.bucket_name:
            try:
                bucket = self._gcs_client.bucket(self.bucket_name)
                blob = bucket.blob("syracuse_session.json")
                if blob.exists():
                    blob.delete()
                    logger.info("Session GCS supprimée.")
            except Exception as e:
                logger.warning(f"Erreur suppression blob GCS session : {e}")

        if self.local_file_path.exists():
            try:
                self.local_file_path.unlink()
                logger.info("Session locale supprimée.")
            except Exception as e:
                logger.warning(f"Erreur suppression session locale : {e}")
