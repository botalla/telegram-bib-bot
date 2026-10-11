"""Tests unitaires pour le service ConversationStore."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.services.conversation_store import ConversationStore


@pytest.fixture
def temp_store(tmp_path, mock_settings):
    """Fixture créant un ConversationStore utilisant un répertoire temporaire."""
    local_dir = tmp_path / "conversations"
    return ConversationStore(settings=mock_settings, bucket_name=None, local_dir=str(local_dir))


def test_add_turn_and_get_history(temp_store):
    """Vérifie l'enregistrement et la restitution d'un tour de conversation."""
    user_id = 12345678

    # Historique vide initialement
    history = temp_store.get_recent_history(user_id=user_id)
    assert history == []

    # Ajout d'un premier échange
    temp_store.add_turn(
        user_id=user_id,
        user_text="Quels sont les emprunts de Camille ?",
        model_text="Camille a 2 livres empruntés : Mortelle Adèle et L'Arabe du futur.",
    )

    history = temp_store.get_recent_history(user_id=user_id)
    assert len(history) == 2
    assert history[0] == {"role": "user", "text": "Quels sont les emprunts de Camille ?"}
    assert history[1] == {"role": "model", "text": "Camille a 2 livres empruntés : Mortelle Adèle et L'Arabe du futur."}


def test_time_window_filtering(temp_store, monkeypatch):
    """Vérifie que seuls les messages de moins de max_hours sont renvoyés."""
    user_id = 12345678
    now = datetime(2026, 10, 11, 14, 0, 0, tzinfo=UTC).timestamp()

    # Simulation d'anciens messages stockés à la main
    raw_data = {
        "telegram_id": user_id,
        "messages": [
            # Message vieux de 6 heures (> 4h) -> doit être ignoré
            {"role": "user", "text": "Vieux message user", "timestamp": now - (6 * 3600)},
            {"role": "model", "text": "Vieux message model", "timestamp": now - (6 * 3600)},
            # Message vieux de 2 heures (< 4h) -> doit être conservé
            {"role": "user", "text": "Message récent user", "timestamp": now - (2 * 3600)},
            {"role": "model", "text": "Message récent model", "timestamp": now - (2 * 3600)},
        ],
    }
    temp_store._write_raw_data(user_id, raw_data)

    # Mock de datetime.now pour correspondre à notre timestamp de test
    mock_dt = MagicMock()
    mock_dt.now.return_value = datetime.fromtimestamp(now, tz=UTC)
    monkeypatch.setattr("src.services.conversation_store.datetime", mock_dt)

    history = temp_store.get_recent_history(user_id=user_id, max_hours=4.0)

    assert len(history) == 2
    assert history[0]["text"] == "Message récent user"
    assert history[1]["text"] == "Message récent model"


def test_role_alternation_and_first_user(temp_store, monkeypatch):
    """Vérifie que l'historique commence toujours par 'user' et alterne strictement."""
    user_id = 12345678
    now = datetime(2026, 10, 11, 14, 0, 0, tzinfo=UTC).timestamp()

    # Supposons qu'après filtrage temporel, le premier message soit 'model',
    # suivi de deux 'user' consécutifs
    raw_data = {
        "telegram_id": user_id,
        "messages": [
            {"role": "model", "text": "Message model orphelin", "timestamp": now - 3600},
            {"role": "user", "text": "Question partie 1", "timestamp": now - 1800},
            {"role": "user", "text": "Question partie 2", "timestamp": now - 1790},
            {"role": "model", "text": "Réponse assistant", "timestamp": now - 1700},
        ],
    }
    temp_store._write_raw_data(user_id, raw_data)

    mock_dt = MagicMock()
    mock_dt.now.return_value = datetime.fromtimestamp(now, tz=UTC)
    monkeypatch.setattr("src.services.conversation_store.datetime", mock_dt)

    history = temp_store.get_recent_history(user_id=user_id, max_hours=4.0)

    # 1. Le model orphelin au début a été sauté
    # 2. Les deux user consécutifs ont été fusionnés
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["text"] == "Question partie 1\nQuestion partie 2"
    assert history[1]["role"] == "model"
    assert history[1]["text"] == "Réponse assistant"


def test_max_messages_limit(temp_store):
    """Vérifie le respect du plafond max_messages."""
    user_id = 12345678

    # Ajout de 10 tours (20 messages au total)
    for i in range(10):
        temp_store.add_turn(user_id, f"User {i}", f"Model {i}")

    # Demande de max 6 messages (3 derniers tours)
    history = temp_store.get_recent_history(user_id=user_id, max_messages=6)
    assert len(history) == 6
    assert history[0]["text"] == "User 7"
    assert history[-1]["text"] == "Model 9"


def test_clear_history(temp_store):
    """Vérifie la suppression de l'historique."""
    user_id = 12345678
    temp_store.add_turn(user_id, "Bonjour", "Bonjour !")
    assert len(temp_store.get_recent_history(user_id)) == 2

    # Clear
    result = temp_store.clear_history(user_id)
    assert result is True
    assert temp_store.get_recent_history(user_id) == []


def test_gcs_operations(monkeypatch, mock_settings):
    """Vérifie les opérations GCS quand GCS est actif."""
    mock_storage_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()

    mock_storage_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    # Simuler blob.exists() et download_as_text()
    mock_blob.exists.return_value = True
    mock_blob.download_as_text.return_value = '{"messages": [{"role": "user", "text": "Test GCS", "timestamp": 9999999999}]}'

    store = ConversationStore(
        settings=mock_settings,
        bucket_name="test-bucket",
        local_dir=".temp_test_cache",
    )
    store._gcs_client = mock_storage_client
    store._gcs_available = True

    # Lecture via GCS
    history = store.get_recent_history(user_id=999)
    assert len(history) == 1
    assert history[0]["text"] == "Test GCS"

    # Écriture via GCS
    store.add_turn(user_id=999, user_text="Hello", model_text="Hi")
    mock_blob.upload_from_string.assert_called_once()

    # Suppression via GCS
    store.clear_history(user_id=999)
    mock_blob.delete.assert_called_once()
