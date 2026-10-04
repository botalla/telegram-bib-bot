"""Agent conversationnel propulsé par Google Gemini avec Function Calling.

Interprète les demandes en langage naturel des utilisateurs Telegram,
déclenche les outils métier appropriés (BibService) et formule des réponses
concises, chaleureuses et adaptées à l'affichage mobile.
"""

import logging
from typing import Any

from src.ai.tools_schema import GEMINI_TOOLS_DECLARATIONS
from src.config import Settings, get_settings
from src.services.bib_service import BibService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Tu es BiblioBot, l'assistant d'IA bienveillant et expert des Bibliothèques de la Ville de Paris.
Tu aides une famille à gérer leurs emprunts de livres, bandes dessinées et jeux sans jamais avoir de retard.

Règles de comportement :
1. Sois chaleureux, concis et parfaitement lisible sur un écran de smartphone Telegram.
2. Utilise des émojis pertinents (📚, 🏛️, ⏳, 🔴 urgent/retard, 🟠 dans les 3 jours, 🟢 confortable, 🔄 prolongation).
3. Utilise les outils (tools) à ta disposition dès que l'utilisateur te pose une question sur les emprunts, les dates, les membres de la famille (ex: Camille, Félicie, Jean), les médiathèques ou souhaite prolonger des documents.
4. Si un emprunt est urgent ou arrive à expiration, propose spontanément de le prolonger.
5. Formate toujours les listes avec des puces claires et regroupe logiquement par bibliothèque ou par membre si pertinent.
6. Ne mentionne jamais de détails techniques internes (cookies, JSON, Syracuse, etc.).
"""


class GeminiAgent:
    """Agent Gemini avec Function Calling pour BiblioBot."""

    def __init__(self, settings: Settings | None = None, bib_service: BibService | None = None):
        self.settings = settings or get_settings()
        self.bib_service = bib_service or BibService(settings=self.settings)
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        """Initialise le client Google Gemini."""
        if not self.settings.gemini_api_key:
            logger.warning("GEMINI_API_KEY absente. L'agent conversationnel fonctionnera en mode restreint.")
            return

        try:
            from google import genai

            self._client = genai.Client(api_key=self.settings.gemini_api_key)
            logger.info(f"Client Google GenAI initialisé avec le modèle : {self.settings.gemini_model}")
        except Exception as e:
            logger.error(f"Erreur d'initialisation du client Google GenAI : {e}")
            self._client = None

    async def _execute_tool_call(self, name: str, args: dict[str, Any]) -> Any:
        """Achemine l'appel d'outil Gemini vers la méthode correspondante du BibService."""
        logger.info(f"Exécution du Tool Call Gemini : {name} avec args={args}")

        try:
            if name == "get_loans":
                loans = await self.bib_service.get_loans(
                    user_name=args.get("user_name"),
                    branch_name=args.get("branch_name"),
                    due_within_days=args.get("due_within_days"),
                )
                return [
                    {
                        "holding_id": str(getattr(loan, "holding_id", "") or getattr(loan, "barcode", "")),
                        "title": loan.title,
                        "account_name": loan.account_name,
                        "library": getattr(loan, "location", None) or getattr(loan, "library", "Bibliothèque"),
                        "due_date": str(loan.due_date) if loan.due_date else None,
                        "is_renewable": getattr(loan, "is_renewable", False),
                    }
                    for loan in loans
                ]

            elif name == "renew_single_loan":
                loan_id = args.get("loan_id", "")
                return await self.bib_service.renew_single_loan(loan_id=loan_id)

            elif name == "renew_expiring_loans":
                within_days = args.get("within_days", 3)
                return await self.bib_service.renew_all_expiring_loans(due_within_days=within_days)

            elif name == "get_branches_summary":
                trips = await self.bib_service.get_trip_planner(branch_filter=args.get("branch_name"))
                return [
                    {
                        "library": t.library,
                        "total_items": t.total_items,
                        "earliest_due_date": str(t.earliest_due_date) if t.earliest_due_date else None,
                        "urgency": getattr(t, "urgency", "normal"),
                        "books": [
                            {
                                "title": item.title,
                                "account_name": item.account_name,
                                "due_date": str(item.due_date) if item.due_date else None,
                            }
                            for item in getattr(t, "loans", [])
                        ],
                    }
                    for t in trips
                ]

            elif name == "get_book_covers":
                user_filter = args.get("user_name")
                loan_ids = args.get("loan_ids")
                covers = await self.bib_service.get_book_covers(loan_ids=loan_ids)
                if user_filter:
                    covers = [c for c in covers if user_filter.lower() in (c.get("account_name") or "").lower()]
                return covers

            elif name == "get_family_members":
                members = await self.bib_service.get_family_members()
                return {"members": members}

            else:
                return {"error": f"Outil '{name}' inconnu."}

        except Exception as e:
            logger.exception(f"Erreur durant l'exécution de l'outil {name} : {e}")
            return {"error": f"Erreur lors de l'exécution : {e!s}"}

    async def chat(self, user_message: str, max_turns: int = 5) -> dict[str, Any]:
        """Traite une question en langage naturel avec Function Calling itératif (Multi-turn ReAct)."""
        if not self._client:
            return {
                "text": "⚠️ L'agent Gemini n'est pas configuré (clé GEMINI_API_KEY manquante). Vous pouvez utiliser les commandes directes comme /emprunts ou /urgences.",
                "tools_used": [],
                "media_urls": [],
            }

        try:
            from google.genai import types

            tools = [types.Tool(function_declarations=GEMINI_TOOLS_DECLARATIONS)]

            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=tools,
                temperature=0.2,
            )

            # Historique de conversation itératif (contents)
            contents: list[Any] = [user_message]
            tools_executed: list[str] = []
            collected_media_urls: list[str] = []

            for turn in range(max_turns):
                logger.info(f"Gemini conversation loop - Tour {turn + 1}/{max_turns}")
                response = self._client.models.generate_content(
                    model=self.settings.gemini_model,
                    contents=contents,
                    config=config,
                )

                function_calls = response.function_calls
                if not function_calls:
                    # Le modèle a formulé sa réponse finale sans demander de nouvel outil
                    final_text = response.text or "Voici les informations demandées."
                    return {
                        "text": final_text,
                        "tools_used": tools_executed,
                        "media_urls": collected_media_urls[:10],
                    }

                # Le modèle a demandé l'exécution d'un ou plusieurs outils
                candidate_content = response.candidates[0].content if response.candidates else None
                if candidate_content:
                    contents.append(candidate_content)

                tool_results_parts = []
                for fc in function_calls:
                    fc_name = fc.name
                    fc_args = dict(fc.args) if fc.args else {}
                    tools_executed.append(fc_name)

                    # Exécution de l'outil
                    result = await self._execute_tool_call(fc_name, fc_args)

                    # Collecte des images si l'outil est get_book_covers
                    if fc_name == "get_book_covers" and isinstance(result, list):
                        for item in result:
                            if isinstance(item, dict) and item.get("cover_url"):
                                if item["cover_url"] not in collected_media_urls:
                                    collected_media_urls.append(item["cover_url"])

                    tool_results_parts.append(
                        types.Part.from_function_response(
                            name=fc_name,
                            response={"result": result},
                        )
                    )

                # Ajout des résultats d'outils au contexte
                contents.append(types.Content(role="user", parts=tool_results_parts))

            # Si on a épuisé le nombre max de tours
            logger.warning(f"Nombre maximum d'itérations ({max_turns}) atteint pour le prompt : {user_message[:50]}...")
            return {
                "text": "J'ai effectué plusieurs vérifications mais je n'ai pas pu finaliser la synthèse. Voici ce que j'ai pu identifier jusqu'ici.",
                "tools_used": tools_executed,
                "media_urls": collected_media_urls[:10],
            }

        except Exception as e:
            logger.exception(f"Erreur lors du traitement Gemini : {e}")
            return {
                "text": "Désolé, j'ai rencontré une difficulté lors de l'analyse de votre demande. Vous pouvez utiliser les commandes directes comme /emprunts ou /urgences.",
                "tools_used": [],
                "media_urls": [],
            }
