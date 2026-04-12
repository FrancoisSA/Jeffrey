#!/usr/bin/env python3
"""
Script simple pour tester l'API Mistral sans outils.
Envoie un prompt et affiche la réponse.
"""

import os
import sys
import logging
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

def test_mistral_simple():
    """Test simple de l'API Mistral."""
    
    # Charger la configuration
    mistral_api_key = os.getenv("MISTRAL_API_KEY")
    
    if not mistral_api_key:
        logger.error("MISTRAL_API_KEY non trouvée dans .env")
        return False
    
    logger.info(f"Clé API Mistral trouvée: {mistral_api_key[:10]}...")
    
    try:
        # Importer le client Mistral
        from mistralai.client import Mistral
        
        # Créer le client
        client = Mistral(api_key=mistral_api_key)
        logger.info("✅ Client Mistral créé avec succès")
        
        # Message de test simple
        test_message = "Dis-moi bonjour en français"
        
        logger.info(f"Envoi du message: '{test_message}'")
        
        # Appeler l'API Mistral
        chat_obj = client.chat
        logger.info(f"Type de chat_obj: {type(chat_obj)}")
        
        # Utiliser la méthode complete
        if hasattr(chat_obj, 'complete'):
            response = chat_obj.complete(
                model="mistral-small-latest",
                messages=[{"role": "user", "content": test_message}],
            )
        else:
            logger.error("❌ Méthode complete non trouvée sur l'objet chat")
            return False
        
        logger.info(f"✅ Réponse reçue:")
        logger.info(f"Type de réponse: {type(response)}")
        logger.info(f"Réponse complète: {response}")
        
        # Extraire le contenu
        if hasattr(response, 'choices') and len(response.choices) > 0:
            content = response.choices[0].message.content
            logger.info(f"\nContenu extrait: {content}")
            return True
        else:
            logger.error("❌ Impossible d'extraire le contenu de la réponse")
            return False
        
    except ImportError as e:
        logger.error(f"❌ Impossible d'importer le client Mistral: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'appel à l'API Mistral: {e}")
        logger.error(f"Type d'erreur: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("="*60)
    logger.info("TEST SIMPLE DE L'API MISTRAL")
    logger.info("="*60)
    
    success = test_mistral_simple()
    
    logger.info("\n" + "="*60)
    if success:
        logger.info("🎉 Test réussi ! L'API Mistral fonctionne correctement.")
        sys.exit(0)
    else:
        logger.error("❌ Test échoué.")
        sys.exit(1)