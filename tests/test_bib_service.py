"""Tests unitaires pour BibService."""

import pytest
from unittest.mock import AsyncMock, patch

from src.services.bib_service import BibService


@pytest.mark.asyncio
async def test_get_loans_filtering(mock_settings, mock_family_data):
    service = BibService(settings=mock_settings)

    with patch.object(service, "get_family_overview", new=AsyncMock(return_value=mock_family_data)):
        # 1. Tous les emprunts
        all_loans = await service.get_loans()
        assert len(all_loans) == 3

        # 2. Filtrer par membre (Camille)
        camille_loans = await service.get_loans(user_name="Camille")
        assert len(camille_loans) == 2
        assert all(l.account_name == "Camille" for l in camille_loans)

        # 3. Filtrer par bibliothèque (Duras)
        duras_loans = await service.get_loans(branch_name="Duras")
        assert len(duras_loans) == 2
        assert all("Duras" in l.library for l in duras_loans)

        # 4. Filtrer par urgence (échéance sous 2 jours)
        urgent_loans = await service.get_loans(due_within_days=2)
        assert len(urgent_loans) == 2  # Jean (J+0) et Camille (J+1)


@pytest.mark.asyncio
async def test_get_family_members(mock_settings, mock_family_data):
    service = BibService(settings=mock_settings)

    with patch.object(service, "get_family_overview", new=AsyncMock(return_value=mock_family_data)):
        members = await service.get_family_members()
        assert "Camille" in members
        assert "Jean" in members
        assert len(members) == 2


@pytest.mark.asyncio
async def test_trip_planner(mock_settings, mock_family_data):
    service = BibService(settings=mock_settings)

    with patch.object(service, "get_family_overview", new=AsyncMock(return_value=mock_family_data)):
        trips = await service.get_trip_planner()
        assert len(trips) == 2
        # La médiathèque avec le livre à rendre aujourd'hui (Václav Havel) doit être en premier
        assert trips[0].library == "Václav Havel"
