"""Schémas des outils (Function Calling) déclarés pour Google Gemini.

Définit les outils métier auxquels l'IA a accès pour interroger et agir
sur les comptes de bibliothèque de la Ville de Paris.
"""

from typing import Any, Dict, List

GEMINI_TOOLS_DECLARATIONS: List[Dict[str, Any]] = [
    {
        "name": "get_loans",
        "description": "Récupère les emprunts en cours pour toute la famille ou selon des filtres précis (nom du membre, nom de la bibliothèque, ou échéance de retour dans X jours).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "user_name": {
                    "type": "STRING",
                    "description": "Nom du titulaire de la carte (ex: 'Camille', 'Félicie', 'Jean'). Optionnel.",
                },
                "branch_name": {
                    "type": "STRING",
                    "description": "Nom de la bibliothèque où ont été empruntés les ouvrages (ex: 'Duras', 'Václav Havel'). Optionnel.",
                },
                "due_within_days": {
                    "type": "INTEGER",
                    "description": "Filtrer les ouvrages qui doivent être rendus d'ici X jours (0 pour aujourd'hui ou en retard). Optionnel.",
                },
            },
        },
    },
    {
        "name": "renew_single_loan",
        "description": "Prolonge la durée d'emprunt d'un livre précis grâce à son identifiant ou son titre exact.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "loan_id": {
                    "type": "STRING",
                    "description": "L'identifiant unique ou code-barres de l'ouvrage à prolonger.",
                },
                "book_title": {
                    "type": "STRING",
                    "description": "Le titre de l'ouvrage pour confirmation (optionnel).",
                },
            },
            "required": ["loan_id"],
        },
    },
    {
        "name": "renew_expiring_loans",
        "description": "Prolonge en une seule opération tous les emprunts arrivant à expiration dans une fenêtre de jours donnée.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "within_days": {
                    "type": "INTEGER",
                    "description": "Seuil en jours (ex: 3 pour tout ce qui expire dans moins de 3 jours). Défaut: 3.",
                }
            },
        },
    },
    {
        "name": "get_branches_summary",
        "description": "Renvoie le récapitulatif des emprunts classé par bibliothèque (Trip Planner) afin d'organiser le sac de retour des livres.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "branch_name": {
                    "type": "STRING",
                    "description": "Filtrer sur une bibliothèque particulière (optionnel).",
                }
            },
        },
    },
    {
        "name": "get_book_covers",
        "description": "Récupère les URLs et métadonnées visuelles des couvertures des livres en cours d'emprunt pour aider à les retrouver à la maison.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "user_name": {
                    "type": "STRING",
                    "description": "Filtrer les couvertures sur un membre particulier (ex: 'Camille'). Optionnel.",
                }
            },
        },
    },
    {
        "name": "get_family_members",
        "description": "Donne la liste de tous les membres de la famille / cartes d'emprunteurs associées au compte.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        },
    },
]
