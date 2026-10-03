"""Générateur de claviers interactifs (Inline Keyboards) pour Telegram."""

from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Clavier du menu d'accueil principal."""
    keyboard = [
        [
            InlineKeyboardButton("📚 Tous les emprunts", callback_data="menu:emprunts"),
            InlineKeyboardButton("🔴 Urgences (< 48h)", callback_data="menu:urgences"),
        ],
        [
            InlineKeyboardButton("👨‍👩‍👧 Emprunts par membre", callback_data="menu:members"),
            InlineKeyboardButton("🎒 Sac de retours (Trip)", callback_data="menu:trips"),
        ],
        [
            InlineKeyboardButton("⚡ Prolonger les urgences", callback_data="renew:expiring"),
            InlineKeyboardButton("🖼️ Voir les couvertures", callback_data="menu:covers"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_members_keyboard(members: List[str]) -> InlineKeyboardMarkup:
    """Clavier pour sélectionner un membre de la famille."""
    keyboard = []
    # Disposition 2 colonnes
    row = []
    for member in members:
        row.append(InlineKeyboardButton(f"👤 {member}", callback_data=f"member:{member}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("🔙 Menu principal", callback_data="menu:main")])
    return InlineKeyboardMarkup(keyboard)


def get_loan_action_keyboard(loan_id: str, is_renewable: bool = True) -> InlineKeyboardMarkup:
    """Clavier sous un livre spécifique."""
    buttons = []
    if is_renewable:
        buttons.append(InlineKeyboardButton("🔄 Prolonger ce livre", callback_data=f"renew:single:{loan_id}"))
    buttons.append(InlineKeyboardButton("🔙 Menu", callback_data="menu:main"))
    return InlineKeyboardMarkup([buttons])


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Clavier simple de retour au menu."""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu principal", callback_data="menu:main")]])
