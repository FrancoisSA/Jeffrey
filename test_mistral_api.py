#!/usr/bin/env python3
"""
Script de test pour vérifier que l'API Mistral fonctionne correctement.
Teste la connexion et les appels de base à l'API Mistral.
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

def test_mistral_api():
    """Teste la connexion et les appels de base à l'API Mistral."""
    
    # Vérifier que la clé API est disponible
    mistral_api_key = os.getenv("MISTRAL_API_KEY")
    if not mistral_api_key:
        logger.error("MISTRAL_API_KEY non trouvée dans .env")
        return False
    
    logger.info(f"Clé API Mistral trouvée: {mistral_api_key[:10]}...")
    
    try:
        # Importer le client Mistral
        from mistralai.client import Mistral
        logger.info("✅ Import du client Mistral réussi")
        
        # Créer le client
        client = Mistral(api_key=mistral_api_key)
        logger.info("✅ Création du client Mistral réussie")
        
        # Tester les différentes méthodes d'appel
        test_messages = [
            {"role": "user", "content": "Dis-moi bonjour en français"}
        ]
        
        # Méthode 1: Essayer chat() directement
        try:
            chat_obj = client.chat
            logger.info(f"Type de chat_obj: {type(chat_obj)}")
            logger.info(f"Attributs de chat_obj: {[a for a in dir(chat_obj) if not a.startswith('_')]}")
            
            # Vérifier si chat_obj a une méthode complete
            if hasattr(chat_obj, 'complete'):
                logger.info("Trouvé méthode complete sur chat_obj")
                response = chat_obj.complete(
                    model="mistral-small-latest",
                    messages=test_messages,
                )
                logger.info("✅ Appel chat_obj.complete() réussi")
                logger.info(f"Type de réponse: {type(response)}")
                logger.info(f"Réponse: {response}")
                return True
            elif hasattr(chat_obj, 'stream'):
                logger.info("Trouvé méthode stream sur chat_obj")
                # Pour le streaming, nous devons itérer
                response = chat_obj.stream(
                    model="mistral-small-latest",
                    messages=test_messages,
                )
                # Consommer le stream
                full_response = ""
                for chunk in response:
                    if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                        if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                            full_response += chunk.choices[0].delta.content
                logger.info("✅ Appel chat_obj.stream() réussi")
                logger.info(f"Réponse: {full_response}")
                return True
            else:
                logger.warning("Aucune méthode complete ou stream trouvée sur chat_obj")
                
            # Essayer d'appeler chat_obj directement (ne devrait pas fonctionner)
            response = chat_obj(
                model="mistral-small-latest",
                messages=test_messages,
            )
            logger.info("✅ Appel chat_obj() réussi")
            logger.info(f"Type de réponse: {type(response)}")
            logger.info(f"Réponse: {response}")
            return True
        except AttributeError as e:
            logger.warning(f"Méthode chat() non disponible: {e}")
        except Exception as e:
            logger.error(f"Erreur avec client.chat(): {e}")
            logger.error(f"Type d'erreur: {type(e).__name__}")
            return False
        
        # Méthode 2: Essayer client.chat.create()
        try:
            if hasattr(client, 'chat') and hasattr(client.chat, 'create'):
                response = client.chat.create(
                    model="mistral-small-latest",
                    messages=test_messages,
                )
                logger.info("✅ Appel client.chat.create() réussi")
                logger.info(f"Type de réponse: {type(response)}")
                logger.info(f"Réponse: {response}")
                return True
        except Exception as e:
            logger.error(f"Erreur avec client.chat.create(): {e}")
        
        # Méthode 3: Essayer d'appeler l'objet chat directement
        try:
            if hasattr(client, 'chat'):
                chat_obj = client.chat
                response = chat_obj(
                    model="mistral-small-latest",
                    messages=test_messages,
                )
                logger.info("✅ Appel client.chat() comme objet réussi")
                logger.info(f"Type de réponse: {type(response)}")
                logger.info(f"Réponse: {response}")
                return True
        except Exception as e:
            logger.error(f"Erreur avec client.chat() comme objet: {e}")
        
        logger.error("❌ Aucune méthode d'appel API Mistral n'a fonctionné")
        return False
        
    except ImportError as e:
        logger.error(f"❌ Impossible d'importer le client Mistral: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Erreur inattendue: {e}")
        return False

if __name__ == "__main__":
    logger.info("Début du test de l'API Mistral...")
    
    success = test_mistral_api()
    
    if success:
        logger.info("\n🎉 Test réussi ! L'API Mistral est opérationnelle.")
        sys.exit(0)
    else:
        logger.error("\n❌ Test échoué. L'API Mistral n'est pas opérationnelle.")
        sys.exit(1)