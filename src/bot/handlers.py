"""Gestionnaires d'événements et commandes Telegram (Handlers).

Gère les commandes (/start, /emprunts, /urgences, /membre, /prolonger, /couvertures, /aide),
les clics de boutons interactifs (CallbackQuery) et le dialogue libre via Gemini.
"""

import logging

from telegram import InputMediaPhoto, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes

from src.ai.gemini_agent import GeminiAgent
from src.bot.formatters import (
    escape,
    format_batch_renewal_report,
    format_loans_list,
    format_trip_planner,
    split_message,
)
from src.bot.keyboards import (
    get_back_to_menu_keyboard,
    get_main_menu_keyboard,
    get_members_keyboard,
)
from src.services.bib_service import BibService

logger = logging.getLogger(__name__)


class BotHandlers:
    """Regroupe l'ensemble des gestionnaires de commandes et messages."""

    def __init__(self, bib_service: BibService | None = None, gemini_agent: GeminiAgent | None = None):
        self.bib_service = bib_service or BibService()
        self.gemini_agent = gemini_agent or GeminiAgent(bib_service=self.bib_service)

    async def _send_or_edit(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        text: str,
        reply_markup=None,
    ) -> None:
        """Envoie ou modifie un message en découpant automatiquement si la taille dépasse 4096 caractères."""
        chunks = split_message(text, max_length=3900)
        chat_id = update.effective_chat.id if update.effective_chat else None

        if update.callback_query and update.callback_query.message:
            first_markup = reply_markup if len(chunks) == 1 else None
            try:
                await update.callback_query.edit_message_text(
                    chunks[0],
                    parse_mode=ParseMode.HTML,
                    reply_markup=first_markup,
                )
            except Exception:
                if chat_id:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=chunks[0],
                        parse_mode=ParseMode.HTML,
                        reply_markup=first_markup,
                    )

            # Envoyer les blocs suivants en nouveaux messages si nécessaire
            for i in range(1, len(chunks)):
                is_last = (i == len(chunks) - 1)
                chunk_markup = reply_markup if is_last else None
                if chat_id:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=chunks[i],
                        parse_mode=ParseMode.HTML,
                        reply_markup=chunk_markup,
                    )
        elif update.message:
            for i, chunk in enumerate(chunks):
                is_last = (i == len(chunks) - 1)
                chunk_markup = reply_markup if is_last else None
                await update.message.reply_text(
                    chunk,
                    parse_mode=ParseMode.HTML,
                    reply_markup=chunk_markup,
                )

    async def start_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Commande /start : Accueil et menu principal."""
        user = update.effective_user
        first_name = user.first_name if user else "Lecteur"

        welcome_text = (
            f"👋 Bonjour <b>{escape(first_name)}</b> !\n\n"
            "Je suis <b>BiblioBot Paris</b>, votre assistant personnel pour les bibliothèques de la Ville de Paris. "
            "Je vous aide à suivre les emprunts de toute la famille, éviter les retards et prolonger vos livres en un clic.\n\n"
            "💬 <i>Vous pouvez m'écrire naturellement (ex: 'Qu'est-ce qu'on doit rendre ?', 'Prolonge les livres de Camille') "
            "ou utiliser les raccourcis ci-dessous :</i>"
        )
        await self._send_or_edit(update, context, welcome_text, reply_markup=get_main_menu_keyboard())

    async def emprunts_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Commande /emprunts : Liste complète des prêts."""
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

        loans = await self.bib_service.get_loans()
        text = format_loans_list(loans, header_title="Tous les emprunts de la famille")
        await self._send_or_edit(update, context, text, reply_markup=get_back_to_menu_keyboard())

    async def urgences_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Commande /urgences : Livres à rendre dans les 48 heures."""
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

        loans = await self.bib_service.get_loans(due_within_days=2)
        text = format_loans_list(loans, header_title="🔴 Emprunts urgents (retour sous 48h)")
        await self._send_or_edit(update, context, text, reply_markup=get_back_to_menu_keyboard())

    async def membre_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Commande /membre [nom] : Emprunts d'un titulaire spécifique."""
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

        args = context.args if context.args else []
        member_name = " ".join(args).strip() if args else None

        if member_name:
            loans = await self.bib_service.get_loans(user_name=member_name)
            text = format_loans_list(loans, header_title=f"Emprunts de {member_name}")
            keyboard = get_back_to_menu_keyboard()
        else:
            members = await self.bib_service.get_family_members()
            if not members:
                text = "ℹ️ Aucun membre n'a pu être détecté automatiquement sur votre compte."
                keyboard = get_back_to_menu_keyboard()
            else:
                text = "👨‍👩‍👧 <b>Choisissez un membre de la famille :</b>"
                keyboard = get_members_keyboard(members)

        await self._send_or_edit(update, context, text, reply_markup=keyboard)

    async def trip_planner_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Organise les retours par bibliothèque."""
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

        trips = await self.bib_service.get_trip_planner()
        text = format_trip_planner(trips)
        await self._send_or_edit(update, context, text, reply_markup=get_back_to_menu_keyboard())

    async def batch_renew_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Commande /prolonger : Prolonge les emprunts qui arrivent à échéance."""
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

        report = await self.bib_service.renew_all_expiring_loans(due_within_days=3)
        text = format_batch_renewal_report(report)
        await self._send_or_edit(update, context, text, reply_markup=get_back_to_menu_keyboard())

    async def covers_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Commande /couvertures : Affiche un album photo des couvertures."""
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)

        covers = await self.bib_service.get_book_covers()
        valid_covers = [c for c in covers if c.get("cover_url")]

        if not valid_covers:
            fallback = "🖼️ Aucune image de couverture n'a pu être récupérée pour vos emprunts actuels."
            if update.message:
                await update.message.reply_text(fallback)
            elif update.callback_query:
                await update.callback_query.message.reply_text(fallback)
            return

        # Limite de 10 photos par envoi dans Telegram MediaGroup
        selected = valid_covers[:10]
        media_group = []

        for item in selected:
            caption = f"📖 <b>{escape(item['title'])}</b>\n👤 {escape(item['account_name'])} | ⏳ {escape(item.get('due_date', ''))}"
            media_group.append(
                InputMediaPhoto(
                    media=item["cover_url"],
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                )
            )

        if chat_id:
            await context.bot.send_media_group(chat_id=chat_id, media=media_group)

    async def help_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Commande /aide : Guide des fonctionnalités."""
        help_text = (
            "ℹ️ <b>Guide d'utilisation de BiblioBot Paris</b>\n\n"
            "<b>Commandes disponibles :</b>\n"
            "• /start — Affiche l'accueil et le menu principal\n"
            "• /emprunts — Liste tous les livres empruntés\n"
            "• /urgences — Liste les livres à rendre sous 48h\n"
            "• /membre [nom] — Affiche les livres d'un membre (ex: <code>/membre Camille</code>)\n"
            "• /prolonger — Prolonge automatiquement les prêts imminents (< 3j)\n"
            "• /couvertures — Affiche les couvertures de vos livres\n"
            "• /aide — Affiche ce message d'aide\n\n"
            "💬 <b>Langage Naturel (IA Gemini) :</b>\n"
            "Vous pouvez aussi simplement m'écrire comme à un ami :\n"
            "<i>• 'Quels sont les livres à rendre aujourd'hui à Duras ?'</i>\n"
            "<i>• 'Prolonge la bande dessinée de Camille'</i>\n"
            "<i>• 'Combien de livres on a en tout ?'</i>\n"
            "<i>• 'Je prépare mon sac pour Václav Havel'</i>"
        )
        await self._send_or_edit(update, context, help_text, reply_markup=get_back_to_menu_keyboard())

    async def text_message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Gestionnaire des messages en langage naturel délégués à Gemini."""
        if not update.message or not update.message.text:
            return

        user_text = update.message.text.strip()
        chat_id = update.effective_chat.id if update.effective_chat else None

        if chat_id:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

        response = await self.gemini_agent.chat(user_text)
        reply_text = response.get("text", "Désolé, je n'ai pas pu traiter votre demande.")
        await self._send_or_edit(update, context, reply_text, reply_markup=get_back_to_menu_keyboard())

    async def callback_query_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Routeur des clics sur les boutons interactifs."""
        query = update.callback_query
        if not query:
            return

        await query.answer()
        data = query.data or ""

        if data == "menu:main":
            await self.start_handler(update, context)
        elif data == "menu:emprunts":
            await self.emprunts_handler(update, context)
        elif data == "menu:urgences":
            await self.urgences_handler(update, context)
        elif data == "menu:members":
            await self.membre_handler(update, context)
        elif data == "menu:trips":
            await self.trip_planner_handler(update, context)
        elif data == "menu:covers":
            await self.covers_handler(update, context)
        elif data == "renew:expiring":
            await self.batch_renew_handler(update, context)
        elif data.startswith("member:"):
            target_member = data.split(":", 1)[1]
            context.args = [target_member]
            await self.membre_handler(update, context)
        elif data.startswith("renew:single:"):
            loan_id = data.split(":", 2)[2]
            res = await self.bib_service.renew_single_loan(loan_id=loan_id)
            status_text = res.get("message", "Opération terminée.")
            await self._send_or_edit(
                update,
                context,
                f"🔄 <b>Résultat :</b>\n\n{escape(status_text)}",
                reply_markup=get_back_to_menu_keyboard(),
            )
