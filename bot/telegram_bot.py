"""
Bot Telegram - Point d'entrée des messages utilisateur.
Reçoit les messages, les transmet à l'agent Mistral, et renvoie la réponse.

Fonctionnalités :
- /start : Message de bienvenue
- /aide : Affiche les commandes disponibles
- /taches : Liste les tâches en cours
- /agenda : Liste les événements des 7 prochains jours
- Messages texte : traités par Mistral en langage naturel
- Messages vocaux : transcrits via Whisper puis traités comme du texte
"""
import logging
import time
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from agent.mistral_agent import process_message
from services.google_tasks import list_tasks
from services.google_calendar import list_events
from services.voice import download_and_transcribe
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from dashboard.journal import log_exchange

logger = logging.getLogger(__name__)

# Historique de conversation par utilisateur (en mémoire, réinitialisé au redémarrage)
# Clé : chat_id, Valeur : liste de messages {role, content}
conversation_histories: dict[int, list] = {}

# Taille maximale de l'historique conservé (nb de tours)
MAX_HISTORY_TURNS = 10


def _get_history(chat_id: int) -> list:
    """Retourne l'historique de conversation pour un chat donné."""
    return conversation_histories.get(chat_id, [])


def _update_history(chat_id: int, user_message: str, assistant_reply: str):
    """
    Met à jour l'historique en ajoutant le dernier échange.
    Limite la taille pour éviter de dépasser le contexte de Claude.
    """
    history = conversation_histories.get(chat_id, [])
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": assistant_reply})

    # Garder seulement les MAX_HISTORY_TURNS derniers tours (2 messages par tour)
    max_messages = MAX_HISTORY_TURNS * 2
    if len(history) > max_messages:
        history = history[-max_messages:]

    conversation_histories[chat_id] = history


def _format_tasks(tasks: list) -> str:
    """Formate une liste de tâches en message Telegram lisible."""
    if not tasks:
        return "Aucune tâche en cours. 🎉"

    lines = ["📋 *Vos tâches :*\n"]
    for t in tasks:
        due = f" _(échéance : {t['due'][:10]})_" if t.get("due") else ""
        lines.append(f"• {t['title']}{due}")
        if t.get("notes"):
            lines.append(f"  _{t['notes']}_")
    return "\n".join(lines)


def _format_events(events: list) -> str:
    """Formate une liste d'événements en message Telegram lisible."""
    if not events:
        return "Aucun événement dans les 7 prochains jours. 📅"

    lines = ["📅 *Agenda des 7 prochains jours :*\n"]
    for e in events:
        start = e.get("start", "")
        # Afficher la date/heure de façon lisible
        if "T" in start:
            from datetime import datetime
            import pytz
            from config import TIMEZONE
            tz = pytz.timezone(TIMEZONE)
            dt = datetime.fromisoformat(start)
            if dt.tzinfo is None:
                dt = tz.localize(dt)
            start_fmt = dt.strftime("%d/%m à %H:%M")
        else:
            start_fmt = start

        lines.append(f"• *{e['summary']}* — {start_fmt}")
        if e.get("location"):
            lines.append(f"  📍 {e['location']}")
    return "\n".join(lines)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /start — message de bienvenue."""
    await update.message.reply_text(
        "👋 Bonjour ! Je suis *Jeffrey*, votre assistant personnel.\n\n"
        "Je peux gérer vos tâches et votre agenda. Parlez-moi naturellement !\n\n"
        "Tapez /aide pour voir les commandes disponibles.",
        parse_mode="Markdown",
    )


async def cmd_aide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /aide — affiche les commandes disponibles."""
    await update.message.reply_text(
        "*Commandes disponibles :*\n\n"
        "/taches — Voir vos tâches en cours\n"
        "/agenda — Voir l'agenda des 7 prochains jours\n"
        "/aide — Afficher cette aide\n\n"
        "*Exemples de messages naturels :*\n"
        "• \"Ajoute une tâche : appeler Jérôme demain à 12h\"\n"
        "• \"Ajoute un RDV avec le notaire le 15/04 à 14h\"\n"
        "• \"Quelles tâches ai-je pour la clim ?\"\n"
        "• \"Marque la tâche [nom] comme terminée\"\n"
        "• \"Supprime le RDV du 15 avril\"\n",
        parse_mode="Markdown",
    )


async def cmd_taches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /taches — affiche les tâches en cours."""
    await update.message.reply_text("⏳ Chargement de vos tâches...")
    try:
        tasks = list_tasks(max_results=20)
        await update.message.reply_text(_format_tasks(tasks), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Erreur /taches : {e}")
        await update.message.reply_text(f"❌ Erreur lors du chargement des tâches : {e}")


async def cmd_agenda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /agenda — affiche l'agenda des 7 prochains jours."""
    await update.message.reply_text("⏳ Chargement de l'agenda...")
    try:
        events = list_events(days_ahead=7)
        await update.message.reply_text(_format_events(events), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Erreur /agenda : {e}")
        await update.message.reply_text(f"❌ Erreur lors du chargement de l'agenda : {e}")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gestionnaire pour les messages vocaux.
    Transcrit le fichier OGG via Whisper, puis traite le texte obtenu
    exactement comme un message texte ordinaire.
    """
    chat_id = update.effective_chat.id

    # Vérifier que le message vient de l'utilisateur autorisé
    if TELEGRAM_CHAT_ID and str(chat_id) != str(TELEGRAM_CHAT_ID):
        logger.warning(f"Message vocal rejeté du chat non autorisé : {chat_id}")
        await update.message.reply_text("❌ Accès non autorisé.")
        return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # Télécharger et transcrire le message vocal
        voice_file = await context.bot.get_file(update.message.voice.file_id)
        transcribed_text = await download_and_transcribe(voice_file)

        if not transcribed_text:
            await update.message.reply_text("🎤 Je n'ai pas compris le message vocal. Pouvez-vous réessayer ?")
            return

        # Informer l'utilisateur de ce qui a été compris
        await update.message.reply_text(f"🎤 _{transcribed_text}_", parse_mode="Markdown")

        # Traiter le texte transcrit comme un message normal
        history = _get_history(chat_id)
        t0 = time.monotonic()
        reply = process_message(transcribed_text, conversation_history=history)
        duration_ms = int((time.monotonic() - t0) * 1000)
        _update_history(chat_id, transcribed_text, reply)

        # Enregistrer l'échange dans le journal du dashboard
        log_exchange(transcribed_text, reply, message_type="voice", duration_ms=duration_ms)

        # Tronquer si nécessaire
        max_length = 3000
        if len(reply) > max_length:
            reply = reply[:max_length] + "\n\n... [message tronqué]"

        await update.message.reply_text(reply, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Erreur lors du traitement du message vocal : {e}")
        await update.message.reply_text(
            f"❌ Erreur lors de la transcription vocale : {e}\n\nEssayez d'envoyer un message texte."
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gestionnaire principal : traite les messages en langage naturel via Claude.
    Envoie d'abord un indicateur de frappe, puis appelle l'agent Claude.
    """
    chat_id = update.effective_chat.id
    user_text = update.message.text

    # Vérifier que le message vient de l'utilisateur autorisé (sécurité basique)
    if TELEGRAM_CHAT_ID and str(chat_id) != str(TELEGRAM_CHAT_ID):
        logger.warning(f"Message rejeté du chat non autorisé : {chat_id}")
        await update.message.reply_text("❌ Accès non autorisé.")
        return

    # Indiquer que le bot traite le message
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        # Récupérer l'historique de conversation
        history = _get_history(chat_id)

        # Appeler l'agent — mesurer la durée pour le journal
        t0 = time.monotonic()
        reply = process_message(user_text, conversation_history=history)
        duration_ms = int((time.monotonic() - t0) * 1000)

        # Mettre à jour l'historique
        _update_history(chat_id, user_text, reply)

        # Enregistrer l'échange dans le journal du dashboard
        log_exchange(user_text, reply, message_type="text", duration_ms=duration_ms)

        # Tronquer le message s'il est trop long (limite Telegram ~4096 caractères)
        max_length = 3000  # Marge de sécurité plus grande
        if len(reply) > max_length:
            original_length = len(reply)
            reply = reply[:max_length] + "\n\n... [message tronqué]"
            logger.warning(f"Message tronqué de {original_length} à {max_length} caractères")

        await update.message.reply_text(reply, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Erreur lors du traitement du message : {e}")
        await update.message.reply_text(
            f"❌ Une erreur s'est produite : {e}\n\nVeuillez réessayer."
        )


def create_application() -> Application:
    """
    Crée et configure l'application Telegram bot.

    Returns:
        Application configurée, prête à démarrer.
    """
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Enregistrer les handlers de commandes
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("aide", cmd_aide))
    app.add_handler(CommandHandler("taches", cmd_taches))
    app.add_handler(CommandHandler("agenda", cmd_agenda))

    # Handler pour tous les messages texte (langage naturel)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Handler pour les messages vocaux (transcription Whisper → Mistral)
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    return app
