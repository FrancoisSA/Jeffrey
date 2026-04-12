"""
Point d'entrée principal de Jeffrey.
Lance le bot Telegram et le scheduler de rappels de façon asynchrone.

Démarrage : python main.py
Dashboard (séparé) : streamlit run dashboard/app.py
"""
import asyncio
import logging
import sys

from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, MISTRAL_API_KEY, GOOGLE_CREDENTIALS_FILE
from bot.telegram_bot import create_application
from services.reminder import ReminderService

# ---------------------------------------------------------
# Configuration du logging
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("jeffrey.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def _check_config():
    """
    Vérifie que toutes les variables de configuration requises sont présentes.
    Arrête le programme si une variable est manquante.
    """
    missing = []

    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
    if not TELEGRAM_CHAT_ID:
        missing.append("TELEGRAM_CHAT_ID")
    if not MISTRAL_API_KEY:
        missing.append("MISTRAL_API_KEY")

    import os
    if not os.path.exists(GOOGLE_CREDENTIALS_FILE):
        missing.append(f"Fichier Google credentials ({GOOGLE_CREDENTIALS_FILE})")

    if missing:
        logger.error("Configuration manquante :")
        for item in missing:
            logger.error(f"  - {item}")
        logger.error("Vérifiez votre fichier .env et que credentials.json est présent.")
        sys.exit(1)


async def main():
    """Fonction principale asynchrone — lance le bot et le scheduler."""
    logger.info("Démarrage de Jeffrey...")

    # Vérification de la configuration
    _check_config()

    # Créer l'application Telegram
    app = create_application()

    # Créer le service de rappels
    reminder_service = ReminderService(bot=app.bot, chat_id=TELEGRAM_CHAT_ID)

    # Initialiser l'application Telegram
    await app.initialize()
    await app.start()

    # Démarrer le scheduler de rappels
    reminder_service.start()

    logger.info("Jeffrey est prêt ! En attente de messages Telegram...")
    logger.info(f"Dashboard disponible via : streamlit run dashboard/app.py")

    # Démarrer le polling Telegram (bloquant jusqu'à arrêt)
    await app.updater.start_polling(drop_pending_updates=True)

    # Garder le processus actif
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Arrêt de Jeffrey...")
    finally:
        # Arrêt propre
        reminder_service.stop()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        logger.info("Jeffrey arrêté proprement.")


if __name__ == "__main__":
    asyncio.run(main())
