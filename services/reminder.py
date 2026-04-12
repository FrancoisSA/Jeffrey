"""
Service de rappels intelligents.
Utilise APScheduler pour vérifier périodiquement les événements Google Calendar
et les tâches Google Tasks à venir, puis envoie des notifications Telegram.

Les rappels sont envoyés :
- Pour les événements Calendar : REMINDER_ADVANCE_MINUTES avant le début
- Pour les tâches Tasks avec due date : le matin du jour d'échéance (9h00)
"""
import asyncio
import logging
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import TIMEZONE, REMINDER_CHECK_INTERVAL, REMINDER_ADVANCE_MINUTES
from services.google_calendar import get_upcoming_events
from services.google_tasks import list_tasks

logger = logging.getLogger(__name__)


class ReminderService:
    """
    Scheduler de rappels.
    Doit être démarré après la création de l'application Telegram
    pour pouvoir envoyer des messages via le bot.
    """

    def __init__(self, bot, chat_id: str):
        """
        Args:
            bot: Instance du bot Telegram (telegram.Bot).
            chat_id: ID du chat Telegram où envoyer les rappels.
        """
        self.bot = bot
        self.chat_id = chat_id
        self.tz = pytz.timezone(TIMEZONE)
        self.scheduler = AsyncIOScheduler(timezone=self.tz)

        # Mémoriser les rappels déjà envoyés pour éviter les doublons
        # Clé : event_id ou task_id, Valeur : datetime du rappel envoyé
        self._sent_reminders: dict[str, datetime] = {}

    def start(self):
        """Démarre le scheduler de rappels."""
        # Vérification des événements imminents toutes les REMINDER_CHECK_INTERVAL secondes
        self.scheduler.add_job(
            self._check_calendar_reminders,
            "interval",
            seconds=REMINDER_CHECK_INTERVAL,
            id="calendar_reminders",
        )

        # Vérification des tâches dues chaque matin à 9h00
        self.scheduler.add_job(
            self._check_task_reminders,
            "cron",
            hour=9,
            minute=0,
            id="task_reminders",
        )

        self.scheduler.start()
        logger.info("Scheduler de rappels démarré.")

    def stop(self):
        """Arrête le scheduler proprement."""
        self.scheduler.shutdown()
        logger.info("Scheduler de rappels arrêté.")

    async def _check_calendar_reminders(self):
        """
        Vérifie les événements Calendar imminents et envoie un rappel Telegram.
        Un rappel est envoyé REMINDER_ADVANCE_MINUTES avant le début de l'événement.
        """
        try:
            events = get_upcoming_events(minutes_ahead=REMINDER_ADVANCE_MINUTES + 1)
            now = datetime.now(self.tz)

            for event in events:
                event_id = event["id"]
                start_str = event["start"]

                if not start_str:
                    continue

                # Parser la date de début
                start_dt = datetime.fromisoformat(start_str)
                if start_dt.tzinfo is None:
                    start_dt = self.tz.localize(start_dt)

                # Vérifier si on est dans la fenêtre de rappel
                delta = start_dt - now
                if timedelta(0) < delta <= timedelta(minutes=REMINDER_ADVANCE_MINUTES):
                    # Éviter les doublons : ne pas renvoyer dans la même heure
                    last_sent = self._sent_reminders.get(event_id)
                    if last_sent and (now - last_sent) < timedelta(hours=1):
                        continue

                    minutes_left = int(delta.total_seconds() / 60)
                    message = (
                        f"⏰ *Rappel* : **{event['summary']}** dans {minutes_left} min\n"
                        f"🕐 {start_dt.strftime('%H:%M')}"
                    )
                    if event.get("location"):
                        message += f"\n📍 {event['location']}"

                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=message,
                        parse_mode="Markdown",
                    )
                    self._sent_reminders[event_id] = now
                    logger.info(f"Rappel envoyé pour l'événement : {event['summary']}")

        except Exception as e:
            logger.error(f"Erreur lors de la vérification des rappels Calendar : {e}")

    async def _check_task_reminders(self):
        """
        Vérifie les tâches Google Tasks dues aujourd'hui ou en retard
        et envoie un récapitulatif Telegram chaque matin.
        """
        try:
            tasks = list_tasks(max_results=50, show_completed=False)
            now = datetime.now(self.tz)
            today = now.date()

            due_today = []
            overdue = []

            for task in tasks:
                due_str = task.get("due")
                if not due_str:
                    continue

                due_dt = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
                due_date = due_dt.astimezone(self.tz).date()

                if due_date == today:
                    due_today.append(task["title"])
                elif due_date < today:
                    overdue.append(task["title"])

            # Construire le message de récapitulatif
            lines = []
            if overdue:
                lines.append("🔴 *Tâches en retard :*")
                lines.extend(f"  • {t}" for t in overdue)
            if due_today:
                lines.append("🟡 *Tâches pour aujourd'hui :*")
                lines.extend(f"  • {t}" for t in due_today)

            if lines:
                message = "📋 *Récapitulatif de vos tâches*\n\n" + "\n".join(lines)
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode="Markdown",
                )
                logger.info(f"Récapitulatif envoyé : {len(due_today)} aujourd'hui, {len(overdue)} en retard.")

        except Exception as e:
            logger.error(f"Erreur lors de la vérification des rappels Tasks : {e}")
