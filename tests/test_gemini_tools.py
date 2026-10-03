"""Tests unitaires pour les schémas d'outils et l'agent Gemini."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

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
