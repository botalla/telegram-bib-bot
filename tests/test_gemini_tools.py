"""Tests unitaires pour les schémas d'outils et l'agent Gemini."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ai.gemini_agent import GeminiAgent
from src.ai.tools_schema import GEMINI_TOOLS_DECLARATIONS


def test_tools_declarations_validity():
    """Vérifie la conformité des schémas d'outils déclarés pour Gemini."""
    names = [t["name"] for t in GEMINI_TOOLS_DECLARATIONS]
    assert "get_loans" in names
    assert "renew_single_loan" in names
    assert "renew_expiring_loans" in names
    assert "get_branches_summary" in names
    assert "get_book_covers" in names
    assert "get_family_members" in names

    for tool in GEMINI_TOOLS_DECLARATIONS:
        assert "name" in tool
        assert "description" in tool
        assert "parameters" in tool
        assert tool["parameters"]["type"] == "OBJECT"


@pytest.mark.asyncio
async def test_gemini_tool_execution_routing(mock_settings):
    """Vérifie le bon acheminement des Tool Calls vers BibService."""
    mock_bib = MagicMock()
    mock_bib.get_loans = AsyncMock(return_value=[])
    mock_bib.renew_single_loan = AsyncMock(return_value={"success": True, "message": "Prolongé"})
    mock_bib.renew_all_expiring_loans = AsyncMock(return_value={"succeeded_count": 1, "failed_count": 0})
    mock_bib.get_family_members = AsyncMock(return_value=["Camille", "Jean"])

    agent = GeminiAgent(settings=mock_settings, bib_service=mock_bib)

    # 1. Test routage get_loans
    res_loans = await agent._execute_tool_call("get_loans", {"user_name": "Camille"})
    assert res_loans == []
    mock_bib.get_loans.assert_awaited_once_with(user_name="Camille", branch_name=None, due_within_days=None)

    # 2. Test routage renew_single_loan
    res_renew = await agent._execute_tool_call("renew_single_loan", {"loan_id": "123"})
    assert res_renew["success"] is True
    mock_bib.renew_single_loan.assert_awaited_once_with(loan_id="123")

    # 3. Test routage get_family_members
    res_members = await agent._execute_tool_call("get_family_members", {})
    assert res_members == {"members": ["Camille", "Jean"]}

    # 4. Test routage get_book_covers avec loan_ids
    mock_bib.get_book_covers = AsyncMock(return_value=[{"loan_id": "456", "title": "Tintin", "cover_url": "https://img.jpg"}])
    res_covers = await agent._execute_tool_call("get_book_covers", {"loan_ids": ["456"]})
    assert len(res_covers) == 1
    mock_bib.get_book_covers.assert_awaited_once_with(loan_ids=["456"])


@pytest.mark.asyncio
async def test_gemini_agent_iterative_chat_loop(mock_settings):
    """Vérifie que GeminiAgent.chat enchaîne plusieurs tours d'appels d'outils (boucle itérative)."""
    mock_bib = MagicMock()
    mock_bib.get_loans = AsyncMock(return_value=[])
    mock_bib.get_book_covers = AsyncMock(return_value=[{"loan_id": "1", "cover_url": "https://img.url/1.jpg"}])

    agent = GeminiAgent(settings=mock_settings, bib_service=mock_bib)

    # Simuler le client Google GenAI
    mock_client = MagicMock()
    agent._client = mock_client

    # Tour 1 : Gemini demande get_loans
    fc1 = MagicMock()
    fc1.name = "get_loans"
    fc1.args = {"user_name": "Camille"}

    resp1 = MagicMock()
    resp1.function_calls = [fc1]
    resp1.candidates = [MagicMock()]
    resp1.text = None

    # Tour 2 : Gemini reçoit les loans et demande get_book_covers
    fc2 = MagicMock()
    fc2.name = "get_book_covers"
    fc2.args = {"loan_ids": ["1"]}

    resp2 = MagicMock()
    resp2.function_calls = [fc2]
    resp2.candidates = [MagicMock()]
    resp2.text = None

    # Tour 3 : Gemini a tout et formule la réponse textuelle finale
    resp3 = MagicMock()
    resp3.function_calls = None
    resp3.candidates = [MagicMock()]
    resp3.text = "Voici les couvertures des livres de Camille !"

    mock_client.models.generate_content.side_effect = [resp1, resp2, resp3]

    result = await agent.chat("Montre-moi les couvertures des livres de Camille", max_turns=5)

    assert result["text"] == "Voici les couvertures des livres de Camille !"
    assert result["tools_used"] == ["get_loans", "get_book_covers"]
    assert result["media_urls"] == ["https://img.url/1.jpg"]
    assert mock_client.models.generate_content.call_count == 3
