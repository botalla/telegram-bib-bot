"""Service métier d'accès aux Bibliothèques de Paris via parisbibpy.

Fournit une interface asynchrone sécurisée au-dessus de la bibliothèque synchrone parisbibpy,
avec gestion automatique du cache de session et reconnexion transparente.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import date

from src.config import Settings, get_settings
from src.services.session_store import SessionStore

logger = logging.getLogger(__name__)


class BibService:
    """Service d'orchestration pour le portail Syracuse des Bibliothèques de Paris."""

    def __init__(self, settings: Optional[Settings] = None, session_store: Optional[SessionStore] = None):
        self.settings = settings or get_settings()
        self.session_store = session_store or SessionStore(
            bucket_name=self.settings.gcs_bucket_name,
            local_file_path=self.settings.local_session_file,
        )

    def _create_client(self, use_cached_session: bool = True):
        """Instancie un client ParisBibClient en injectant si possible les cookies de session."""
        from parisbibpy import ParisBibClient

        cookies = self.session_store.load_session() if use_cached_session else None

        client = ParisBibClient(
            username=self.settings.parisbib_username,
            password=self.settings.parisbib_password,
            session_cookies=cookies,
        )
        return client

    def _sync_get_family(self) -> Any:
        """Exécution synchrone de la récupération de l'état familial multi-cartes."""
        from parisbibpy.exceptions import AuthenticationError

        # 1. Tentative avec session en cache
        try:
            with self._create_client(use_cached_session=True) as client:
                family = client.get_family()
                # Sauvegarder les cookies actuels si disponibles
                if hasattr(client, "session") and hasattr(client.session, "cookies"):
                    current_cookies = dict(client.session.cookies.items())
                    if current_cookies:
                        self.session_store.save_session(current_cookies)
                return family
        except AuthenticationError:
            logger.warning("Session Syracuse expirée ou invalide. Ré-authentification...")
            self.session_store.clear_session()

        # 2. Reconnexion complète avec identifiants
        with self._create_client(use_cached_session=False) as client:
            client.login()
            family = client.get_family()
            if hasattr(client, "session") and hasattr(client.session, "cookies"):
                current_cookies = dict(client.session.cookies.items())
                if current_cookies:
                    self.session_store.save_session(current_cookies)
            return family

    async def get_family_overview(self) -> Any:
        """Récupère l'ensemble des données familiales (asynchrone, non-bloquant)."""
        return await asyncio.to_thread(self._sync_get_family)

    async def get_loans(
        self,
        user_name: Optional[str] = None,
        branch_name: Optional[str] = None,
        due_within_days: Optional[int] = None,
    ) -> List[Any]:
        """Récupère et filtre la liste des emprunts multi-cartes."""
        family = await self.get_family_overview()
        loans = family.loans

        if user_name:
            user_clean = user_name.strip().lower()
            loans = [
                loan for loan in loans
                if user_clean in (loan.account_name or "").lower()
            ]

        if branch_name:
            branch_clean = branch_name.strip().lower()
            loans = [
                loan for loan in loans
                if branch_clean in (loan.library or "").lower()
            ]

        if due_within_days is not None:
            today = date.today()
            loans = [
                loan for loan in loans
                if loan.due_date and (loan.due_date - today).days <= due_within_days
            ]

        # Tri chronologique par date d'échéance
        return sorted(loans, key=lambda x: x.due_date or date.max)

    async def get_family_members(self) -> List[str]:
        """Retourne les noms de toutes les personnes associées au compte."""
        family = await self.get_family_overview()
        members = []
        for account in family.accounts:
            if account.account_name and account.account_name not in members:
                members.append(account.account_name)
        return members

    def _sync_renew_single_loan(self, loan_id: str) -> Dict[str, Any]:
        """Prolonge un prêt spécifique de manière synchrone."""
        from parisbibpy.exceptions import AuthenticationError

        def _execute_renewal(use_cache: bool):
            with self._create_client(use_cached_session=use_cache) as client:
                family = client.get_family()
                target_loan = None
                target_user_uid = None

                for acc in family.accounts:
                    for loan in acc.loans:
                        # Comparaison avec holding_id ou barcode
                        if str(getattr(loan, "holding_id", "")) == str(loan_id) or str(getattr(loan, "barcode", "")) == str(loan_id):
                            target_loan = loan
                            target_user_uid = acc.unique_identifier
                            break
                    if target_loan:
                        break

                if not target_loan:
                    return {
                        "success": False,
                        "message": f"Prêt introuvable pour l'identifiant {loan_id}.",
                        "loan_id": loan_id,
                    }

                report = client.renew_loans([target_loan], user_unique_identifier=target_user_uid)
                if report.succeeded:
                    succ = report.succeeded[0]
                    return {
                        "success": True,
                        "title": target_loan.title,
                        "account_name": target_loan.account_name,
                        "new_due_date": str(succ.new_due_date) if hasattr(succ, "new_due_date") else None,
                        "message": f"Livre '{target_loan.title}' prolongé avec succès !",
                    }
                else:
                    fail_reason = "Prolongation impossible (quota atteint ou livre réservé)."
                    if report.failed:
                        fail_reason = report.failed[0].reason
                    return {
                        "success": False,
                        "title": target_loan.title,
                        "account_name": target_loan.account_name,
                        "message": f"Échec de prolongation pour '{target_loan.title}' : {fail_reason}",
                    }

        try:
            return _execute_renewal(use_cache=True)
        except AuthenticationError:
            self.session_store.clear_session()
            return _execute_renewal(use_cache=False)

    async def renew_single_loan(self, loan_id: str) -> Dict[str, Any]:
        """Prolonge un prêt spécifique (asynchrone)."""
        return await asyncio.to_thread(self._sync_renew_single_loan, loan_id)

    def _sync_renew_all_expiring(self, due_within_days: int = 3) -> Dict[str, Any]:
        """Prolonge en masse les prêts expirant bientôt."""
        from parisbibpy.exceptions import AuthenticationError

        def _execute_batch(use_cache: bool):
            with self._create_client(use_cached_session=use_cache) as client:
                report = client.renew_all_family_loans(due_within_days=due_within_days)
                return {
                    "succeeded_count": len(report.succeeded),
                    "failed_count": len(report.failed),
                    "succeeded": [
                        {
                            "title": getattr(item, "title", "Ouvrage"),
                            "new_due_date": str(getattr(item, "new_due_date", "")),
                        }
                        for item in report.succeeded
                    ],
                    "failed": [
                        {
                            "title": getattr(item, "title", "Ouvrage"),
                            "reason": getattr(item, "reason", "Non éligible"),
                        }
                        for item in report.failed
                    ],
                }

        try:
            return _execute_batch(use_cache=True)
        except AuthenticationError:
            self.session_store.clear_session()
            return _execute_batch(use_cache=False)

    async def renew_all_expiring_loans(self, due_within_days: int = 3) -> Dict[str, Any]:
        """Prolonge tous les prêts de la famille arrivant à échéance (asynchrone)."""
        return await asyncio.to_thread(self._sync_renew_all_expiring, due_within_days)

    async def get_trip_planner(self, branch_filter: Optional[str] = None) -> List[Any]:
        """Retourne la liste des bibliothèques ordonnées par urgence de retour (Trip Planner)."""
        family = await self.get_family_overview()
        trips = family.plan_library_trips()

        if branch_filter:
            bf_clean = branch_filter.strip().lower()
            trips = [t for t in trips if bf_clean in (t.library or "").lower()]

        return trips

    async def get_book_covers(self, loan_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Récupère les informations visuelles (couvertures) des livres empruntés."""
        family = await self.get_family_overview()
        results = []

        for loan in family.loans:
            lid = str(getattr(loan, "holding_id", "")) or str(getattr(loan, "barcode", ""))
            if loan_ids and lid not in loan_ids:
                continue

            thumbnail = getattr(loan, "thumbnail_url", None) or getattr(loan, "default_thumbnail_url", None)
            results.append({
                "loan_id": lid,
                "title": loan.title,
                "account_name": loan.account_name,
                "due_date": str(loan.due_date) if loan.due_date else None,
                "library": loan.library,
                "cover_url": thumbnail,
            })

        return results
