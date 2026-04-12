#!/usr/bin/env python3
"""
Test complet de Jeffrey : envoie un message réel via l'API Telegram
et affiche la réponse complète.
"""

import os
import sys
import logging
import requests
import json
from dotenv import load_dotenv

# Charger la configuration
load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

def send_telegram_message(token, chat_id, text):
    """Envoye un message via l'API Telegram."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur lors de l'envoi du message Telegram: {e}")
        return None

def get_telegram_updates(token, offset=None):
    """Récupère les mises à jour (réponses) de Telegram."""
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur lors de la récupération des mises à jour: {e}")
        return None

def test_jeffrey_full():
    """Test complet : envoie un message et attend la réponse."""
    
    # Charger la configuration
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not telegram_token or not telegram_chat_id:
        logger.error("Configuration Telegram manquante dans .env")
        return False
    
    logger.info(f"Configuration chargée - Token: {telegram_token[:10]}... Chat ID: {telegram_chat_id}")
    
    # Message de test
    test_message = "Bonjour Jeffrey ! Comment ça va aujourd'hui ?"
    
    # Étape 1: Envoyer le message
    logger.info(f"Envoi du message: '{test_message}'")
    send_response = send_telegram_message(telegram_token, telegram_chat_id, test_message)
    
    if not send_response or not send_response.get("ok"):
        logger.error(f"Échec de l'envoi du message: {send_response}")
        return False
    
    message_id = send_response.get("result", {}).get("message_id")
    logger.info(f"✅ Message envoyé avec succès (ID: {message_id})")
    
    # Étape 2: Attendre et récupérer la réponse
    logger.info("Attente de la réponse de Jeffrey... (timeout: 30s)")
    
    # Récupérer l'offset actuel
    updates = get_telegram_updates(telegram_token)
    if updates and updates.get("result"):
        last_update_id = max(update["update_id"] for update in updates["result"])
        offset = last_update_id + 1
    else:
        offset = None
    
    # Attendre la réponse (avec timeout)
    import time
    start_time = time.time()
    timeout = 30
    
    while time.time() - start_time < timeout:
        updates = get_telegram_updates(telegram_token, offset)
        
        if updates and updates.get("ok") and updates.get("result"):
            for update in updates["result"]:
                if update.get("message", {}).get("from", {}).get("is_bot"):
                    # C'est une réponse du bot
                    response_text = update["message"].get("text", "(pas de texte)")
                    logger.info(f"✅ Réponse reçue: '{response_text}'")
                    return True
        
        time.sleep(1)
    
    logger.error(f"❌ Aucun message de réponse reçu après {timeout} secondes")
    return False

if __name__ == "__main__":
    logger.info("Début du test complet de Jeffrey...")
    logger.info("=" * 60)
    
    success = test_jeffrey_full()
    
    logger.info("=" * 60)
    if success:
        logger.info("\n🎉 Test complet réussi ! Jeffrey répond correctement.")
        sys.exit(0)
    else:
        logger.error("\n❌ Test échoué. Jeffrey n'a pas répondu.")
        sys.exit(1)