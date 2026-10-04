"""Formatage des messages et rendu visuel HTML pour Telegram.

Gère les codes couleurs émojis (🔴/🟠/🟢), la mise en page des listes d'emprunts
et les récapitulatifs du Trip Planner pour smartphone.
"""

import html
from datetime import date
from typing import Any


def escape(text: Any) -> str:
    """Échappe les caractères spéciaux pour le mode HTML de Telegram."""
    if text is None:
        return ""
    return html.escape(str(text))


def get_due_badge(due_date: date | None) -> str:
    """Renvoie un badge visuel et le libellé relatif de l'échéance."""
    if not due_date:
        return "⚪ Date inconnue"

    today = date.today()
    delta = (due_date - today).days

    if delta < 0:
        return f"🔴 <b>EN RETARD de {abs(delta)} j.</b> ({due_date.strftime('%d/%m/%Y')})"
    elif delta == 0:
        return f"🔴 <b>À RENDRE AUJOURD'HUI !</b> ({due_date.strftime('%d/%m/%Y')})"
    elif delta == 1:
        return f"🔴 <b>À rendre demain</b> ({due_date.strftime('%d/%m/%Y')})"
    elif delta <= 3:
        return f"🟠 <b>Dans {delta} jours</b> ({due_date.strftime('%d/%m/%Y')})"
    elif delta <= 7:
        return f"🟡 Dans {delta} jours ({due_date.strftime('%d/%m/%Y')})"
    else:
        return f"🟢 Dans {delta} jours ({due_date.strftime('%d/%m/%Y')})"


def format_loan_item(loan: Any, index: int | None = None) -> str:
    """Formate un prêt individuel avec ses métadonnées."""
    prefix = f"{index}. " if index else "• "
    title = escape(getattr(loan, "title", "Ouvrage sans titre"))
    account = escape(getattr(loan, "account_name", "Titulaire inconnu"))
    library = escape(getattr(loan, "location", None) or getattr(loan, "library", "Bibliothèque"))
    due_badge = get_due_badge(getattr(loan, "due_date", None))
    renewal_count = getattr(loan, "renewal_count", 0)

    renew_str = f"🔄 Prolongé {renewal_count}/2 fois"
    if not getattr(loan, "is_renewable", True):
        renew_str += " (non prolongeable)"

    return (
        f"{prefix}📖 <b>{title}</b>\n"
        f"   👤 {account} | 🏛️ {library}\n"
        f"   ⏳ {due_badge}\n"
        f"   {renew_str}\n"
    )


def format_loans_list(loans: list[Any], header_title: str = "Emprunts en cours") -> str:
    """Formate une liste complète d'emprunts."""
    if not loans:
        return f"📚 <b>{escape(header_title)}</b>\n\nAucun livre emprunté actuellement ! 🎉"

    total = len(loans)
    msg = [f"📚 <b>{escape(header_title)}</b> ({total} ouvrage{'s' if total > 1 else ''}) :\n"]

    for idx, loan in enumerate(loans, 1):
        msg.append(format_loan_item(loan, index=idx))

    return "\n".join(msg)


def format_trip_planner(trips: list[Any]) -> str:
    """Formate la liste ordonnée par bibliothèque pour préparer le sac de retours."""
    if not trips:
        return "🎒 <b>Planificateur de retours (Trip Planner)</b>\n\nAucun retour de livre nécessaire pour l'instant ! 🎉"

    msg = ["🎒 <b>Planificateur de retours par bibliothèque</b> :\n"]

    for trip in trips:
        lib = escape(trip.library)
        total = trip.total_items
        earliest = trip.earliest_due_date.strftime("%d/%m/%Y") if trip.earliest_due_date else "N/A"

        msg.append(f"🏛️ <b>{lib}</b> ({total} document{'s' if total > 1 else ''})")
        msg.append(f"⏳ Plus proche retour : <b>{earliest}</b>")

        for item in getattr(trip, "loans", []):
            acc = escape(getattr(item, "account_name", ""))
            tit = escape(getattr(item, "title", ""))
            due = get_due_badge(getattr(item, "due_date", None))
            msg.append(f"  • {tit} ({acc}) — {due}")

        msg.append("")

    return "\n".join(msg)


def format_batch_renewal_report(report_data: dict) -> str:
    """Formate le rapport de prolongation groupée."""
    succ = report_data.get("succeeded", [])
    fail = report_data.get("failed", [])

    msg = ["⚡ <b>Rapport de prolongation automatique</b> :\n"]

    if succ:
        msg.append(f"✅ <b>{len(succ)} ouvrage(s) prolongé(s) avec succès :</b>")
        for item in succ:
            title = escape(item.get("title", ""))
            new_date = escape(item.get("new_due_date", ""))
            msg.append(f"  • 📖 {title} ➜ Nouveau terme : <b>{new_date}</b>")
        msg.append("")

    if fail:
        msg.append(f"⚠️ <b>{len(fail)} ouvrage(s) non prolongeable(s) :</b>")
        for item in fail:
            title = escape(item.get("title", ""))
            reason = escape(item.get("reason", "Raison non spécifiée"))
            msg.append(f"  • 📖 {title} ➜ ❌ {reason}")
        msg.append("")

    if not succ and not fail:
        msg.append("ℹ️ Aucun livre n'était éligible à la prolongation.")

    return "\n".join(msg)


def split_message(text: str, max_length: int = 3900) -> list[str]:
    """Découpe un texte long en blocs respectant la limite de caractères de Telegram (4096)."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    lines = text.split("\n")
    current_chunk: list[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1
        if current_len + line_len > max_length:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_len = line_len
            else:
                chunks.append(line[:max_length])
                current_chunk = [line[max_length:]]
                current_len = len(current_chunk[0])
        else:
            current_chunk.append(line)
            current_len += line_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks
