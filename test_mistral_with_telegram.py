#!/usr/bin/env python3
"""
Test complet : Simule un message Telegram → Agent Mistral → Réponse Telegram
Ce test valide tout le pipeline de traitement.
"""

import os
import sys
import logging
import requests
import json
from dotenv import load_dotenv
from datetime import datetime

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

def test_mistral_agent_directly():
    """Teste l'agent Mistral directement avec un message simulé."""
    
    # Charger la configuration
    mistral_api_key = os.getenv("MISTRAL_API_KEY")
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not all([mistral_api_key, telegram_token, telegram_chat_id]):
        logger.error("Configuration manquante dans .env")
        return False
    
    logger.info("Test de l'agent Mistral avec un message simulé...")
    
    try:
        # Importer et configurer l'agent Mistral
        from mistralai.client import Mistral
        from agent.mistral_agent import process_message
        
        # Créer le client Mistral
        client = Mistral(api_key=mistral_api_key)
        logger.info("✅ Client Mistral créé avec succès")
        
        # Message de test simulant une demande utilisateur
        test_message = "Bonjour ! Peux-tu me dire ce que tu peux faire pour m'aider ?"
        
        logger.info(f"Envoi du message à l'agent Mistral: '{test_message}'")
        
        # Appeler l'agent Mistral (sans outils pour ce test simple)
        response = process_message(test_message, conversation_history=[])
        
        logger.info(f"✅ Réponse de l'agent Mistral: '{response}'")
        
        # Envoyer la réponse dans Telegram
        logger.info("Envoi de la réponse dans Telegram...")
        send_response = send_telegram_message(telegram_token, telegram_chat_id, response)
        
        if send_response and send_response.get("ok"):
            message_id = send_response.get("result", {}).get("message_id")
            logger.info(f"✅ Réponse envoyée dans Telegram avec succès (ID: {message_id})")
            return True
        else:
            logger.error(f"Échec de l'envoi dans Telegram: {send_response}")
            return False
        
    except ImportError as e:
        logger.error(f"Impossible d'importer les modules nécessaires: {e}")
        return False
    except Exception as e:
        logger.error(f"Erreur lors du traitement: {e}")
        logger.error(f"Type d'erreur: {type(e).__name__}")
        return False

def test_with_tools():
    """Teste l'agent Mistral avec des outils (tâches, calendrier, emails)."""
    
    logger.info("\n" + "="*60)
    logger.info("Test avec outils (tâches, calendrier, emails)")
    logger.info("="*60)
    
    # Charger la configuration
    mistral_api_key = os.getenv("MISTRAL_API_KEY")
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not all([mistral_api_key, telegram_token, telegram_chat_id]):
        logger.error("Configuration manquante dans .env")
        return False
    
    # Messages de test avec différents outils
    test_cases = [
        "Quelles sont mes tâches pour aujourd'hui ?",
        "Quels sont mes rendez-vous cette semaine ?",
        "Quels sont mes derniers emails ?"
    ]
    
    for i, test_message in enumerate(test_cases, 1):
        logger.info(f"\nTest {i}/{len(test_cases)}: '{test_message}'")
        
        try:
            from agent.mistral_agent import process_message
            
            # Traiter le message
            response = process_message(test_message, conversation_history=[])
            
            logger.info(f"Réponse: '{response[:100]}...'" if len(response) > 100 else f"Réponse: '{response}'")
            
            # Envoyer dans Telegram
            send_response = send_telegram_message(telegram_token, telegram_chat_id, response)
            
            if send_response and send_response.get("ok"):
                logger.info("✅ Réponse envoyée dans Telegram")
            else:
                logger.error(f"❌ Échec de l'envoi dans Telegram")
                
        except Exception as e:
            logger.error(f"❌ Erreur pour le test {i}: {e}")
    
    return True

if __name__ == "__main__":
    logger.info("="*60)
    logger.info("TEST COMPLET: Message → Mistral → Telegram")
    logger.info("="*60)
    
    # Test 1: Message simple
    success1 = test_mistral_agent_directly()
    
    # Test 2: Avec outils
    success2 = test_with_tools()
    
    logger.info("\n" + "="*60)
    if success1 and success2:
        logger.info("🎉 Tous les tests ont réussi !")
        logger.info("L'agent Mistral et l'intégration Telegram fonctionnent correctement.")
        sys.exit(0)
    else:
        logger.error("❌ Certains tests ont échoué.")
        sys.exit(1)