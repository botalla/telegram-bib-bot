"""Fixtures et mocks partagés pour la suite de tests pytest."""

from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from src.config import Settings


@dataclass
class MockLoan:
    holding_id: str
    barcode: str
    title: str
    account_name: str
    library: str
    due_date: date
    location: str = ""
    is_renewable: bool = True
    renewal_count: int = 0
    thumbnail_url: str | None = "https://example.com/cover.jpg"
    default_thumbnail_url: str | None = None

    def __post_init__(self):
        if not self.location:
            self.location = self.library


@dataclass
class MockAccount:
    account_name: str
    unique_identifier: str | None
    loans: list[MockLoan]


@dataclass
class MockLibraryTrip:
    library: str
    total_items: int
    earliest_due_date: date
    loans: list[MockLoan]


class MockFamilyOverview:
    def __init__(self, accounts: list[MockAccount]):
        self.accounts = accounts

    @property
    def loans(self) -> list[MockLoan]:
        all_loans = []
        for acc in self.accounts:
            all_loans.extend(acc.loans)
        return all_loans

    def plan_library_trips(self) -> list[MockLibraryTrip]:
        trips = {}
        for loan in self.loans:
            if loan.library not in trips:
                trips[loan.library] = []
            trips[loan.library].append(loan)

        res = []
        for lib, l_list in trips.items():
            earliest = min((loan_item.due_date for loan_item in l_list), default=date.today())
            res.append(
                MockLibraryTrip(
                    library=lib,
                    total_items=len(l_list),
                    earliest_due_date=earliest,
                    loans=l_list,
                )
            )
        return sorted(res, key=lambda x: x.earliest_due_date)


@pytest.fixture
def mock_settings():
    return Settings(
        telegram_bot_token="123456:TEST_TOKEN",
        telegram_webhook_secret="test_secret_token_123",
        allowed_user_ids="12345678,87654321",
        gemini_api_key="TEST_GEMINI_KEY",
        parisbib_username="22272392000000",
        parisbib_password="TEST_PASSWORD",
        local_session_file=".test_session.json",
        environment="test",
    )


@pytest.fixture
def mock_family_data():
    today = date.today()
    loan1 = MockLoan(
        holding_id="HOLD_001",
        barcode="BAR_001",
        title="Mortelle Adèle - Tome 12",
        account_name="Camille",
        library="Marguerite Duras",
        due_date=today + timedelta(days=1),
        is_renewable=True,
    )
    loan2 = MockLoan(
        holding_id="HOLD_002",
        barcode="BAR_002",
        title="L'Arabe du futur 4",
        account_name="Camille",
        library="Marguerite Duras",
        due_date=today + timedelta(days=15),
        is_renewable=False,
        renewal_count=2,
    )
    loan3 = MockLoan(
        holding_id="HOLD_003",
        barcode="BAR_003",
        title="Le problème à 3 corps",
        account_name="Jean",
        library="Václav Havel",
        due_date=today,
        is_renewable=True,
    )

    acc_camille = MockAccount(account_name="Camille", unique_identifier="GUID_CAMILLE", loans=[loan1, loan2])
    acc_jean = MockAccount(account_name="Jean", unique_identifier=None, loans=[loan3])

    return MockFamilyOverview(accounts=[acc_camille, acc_jean])
