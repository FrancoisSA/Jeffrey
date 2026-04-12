"""
Configuration centrale de Jeffrey.
Charge les variables d'environnement depuis le fichier .env
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Mistral
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# Google
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", "token.json")

# Scopes Google nécessaires pour Tasks, Calendar et Gmail
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
]

# Timezone
TIMEZONE = os.getenv("TIMEZONE", "Europe/Paris")

# Fréquence de vérification des rappels (en secondes)
REMINDER_CHECK_INTERVAL = 60

# Délai avant un événement pour envoyer un rappel (en minutes)
REMINDER_ADVANCE_MINUTES = 15
