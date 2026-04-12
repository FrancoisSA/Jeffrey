"""
Agent Mistral avec Tool Use.
Reçoit les messages Telegram en langage naturel (français),
analyse l'intention et appelle les outils Google Tasks / Calendar appropriés.

Les outils disponibles sont déclarés sous forme de JSON Schema et envoyés à Mistral
qui décide quel outil appeler et avec quels arguments.
"""
import json
import logging
from datetime import datetime

from mistralai import Mistral
import pytz

from config import MISTRAL_API_KEY, TIMEZONE
from services.google_tasks import (
    list_tasks,
    add_task,
    complete_task,
    delete_task,
    update_task,
    search_tasks,
)
from services.google_calendar import (
    list_events,
    add_event,
    update_event,
    delete_event,
    search_events,
)
from services.google_gmail import (
    list_emails,
    search_emails,
    get_email,
    mark_as_read,
    mark_as_unread,
)

logger = logging.getLogger(__name__)

# Client Mistral
client = Mistral(api_key=MISTRAL_API_KEY)

# Modèle à utiliser
MODEL = "mistral-small-latest"

# ---------------------------------------------------------
# Définition des outils exposés à Mistral
# ---------------------------------------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "Liste les tâches Google Tasks à faire. Utiliser pour afficher les tâches en cours.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Nombre maximum de tâches à retourner (défaut: 20).",
                    },
                    "show_completed": {
                        "type": "boolean",
                        "description": "Inclure les tâches complétées (défaut: false).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": "Ajoute une nouvelle tâche dans Google Tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Titre de la tâche.",
                    },
                    "due": {
                        "type": "string",
                        "description": "Date/heure d'échéance au format ISO 8601 (ex: '2024-04-15T12:00:00'). Optionnel.",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Notes ou description de la tâche. Optionnel.",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Marque une tâche comme complétée/terminée.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "L'ID de la tâche à compléter.",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Supprime définitivement une tâche.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "L'ID de la tâche à supprimer.",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Modifie une tâche existante (titre, date, notes).",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "L'ID de la tâche à modifier.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Nouveau titre (optionnel).",
                    },
                    "due": {
                        "type": "string",
                        "description": "Nouvelle date d'échéance ISO 8601 (optionnel).",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Nouvelles notes (optionnel).",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_tasks",
            "description": "Recherche des tâches par mot-clé dans le titre ou les notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Mot-clé à rechercher dans les tâches.",
                    },
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_events",
            "description": "Liste les événements Google Calendar à venir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ahead": {
                        "type": "integer",
                        "description": "Nombre de jours à regarder en avant (défaut: 7).",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Nombre maximum d'événements (défaut: 20).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_event",
            "description": "Ajoute un événement dans Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Titre de l'événement.",
                    },
                    "start": {
                        "type": "string",
                        "description": "Datetime de début au format ISO 8601 (ex: '2024-04-15T14:00:00').",
                    },
                    "end": {
                        "type": "string",
                        "description": "Datetime de fin ISO 8601. Si absent, durée d'1h par défaut.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Description / notes de l'événement. Optionnel.",
                    },
                    "location": {
                        "type": "string",
                        "description": "Lieu de l'événement. Optionnel.",
                    },
                },
                "required": ["summary", "start"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_event",
            "description": "Modifie un événement Google Calendar existant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "L'ID Google de l'événement à modifier.",
                    },
                    "summary": {"type": "string", "description": "Nouveau titre. Optionnel."},
                    "start": {"type": "string", "description": "Nouveau début ISO 8601. Optionnel."},
                    "end": {"type": "string", "description": "Nouvelle fin ISO 8601. Optionnel."},
                    "description": {"type": "string", "description": "Nouvelle description. Optionnel."},
                    "location": {"type": "string", "description": "Nouveau lieu. Optionnel."},
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_event",
            "description": "Supprime définitivement un événement du calendrier.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "L'ID Google de l'événement à supprimer.",
                    },
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_events",
            "description": "Recherche des événements par mot-clé dans le calendrier.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Mot-clé à rechercher.",
                    },
                    "days_ahead": {
                        "type": "integer",
                        "description": "Plage de recherche en jours (défaut: 30).",
                    },
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_emails",
            "description": "Liste les emails récents dans la boîte de réception.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Nombre maximum d'emails à retourner (défaut: 10).",
                    },
                    "days_back": {
                        "type": "integer",
                        "description": "Nombre de jours en arrière (défaut: 7).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_emails",
            "description": "Recherche des emails contenant un mot-clé.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Mot-clé à rechercher dans les emails.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Nombre maximum de résultats (défaut: 10).",
                    },
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_email",
            "description": "Récupère le contenu complet d'un email spécifique.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "L'ID de l'email à récupérer.",
                    },
                },
                "required": ["email_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_as_read",
            "description": "Marque un email comme lu.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "L'ID de l'email à marquer comme lu.",
                    },
                },
                "required": ["email_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_as_unread",
            "description": "Marque un email comme non lu.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "L'ID de l'email à marquer comme non lu.",
                    },
                },
                "required": ["email_id"],
            },
        },
    },
]

# ---------------------------------------------------------
# Dispatch des appels d'outils
# ---------------------------------------------------------
TOOL_FUNCTIONS = {
    "list_tasks": lambda args: list_tasks(**args),
    "add_task": lambda args: add_task(**args),
    "complete_task": lambda args: complete_task(**args),
    "delete_task": lambda args: delete_task(**args),
    "update_task": lambda args: update_task(**args),
    "search_tasks": lambda args: search_tasks(**args),
    "list_events": lambda args: list_events(**args),
    "add_event": lambda args: add_event(**args),
    "update_event": lambda args: update_event(**args),
    "delete_event": lambda args: delete_event(**args),
    "search_events": lambda args: search_events(**args),
    "list_emails": lambda args: list_emails(**args),
    "search_emails": lambda args: search_emails(**args),
    "get_email": lambda args: get_email(**args),
    "mark_as_read": lambda args: mark_as_read(**args),
    "mark_as_unread": lambda args: mark_as_unread(**args),
}


def _execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    Exécute l'outil demandé par Mistral et retourne le résultat en JSON.

    Args:
        tool_name: Nom de l'outil à appeler.
        tool_input: Arguments de l'outil.

    Returns:
        Résultat sérialisé en JSON string.
    """
    if tool_name not in TOOL_FUNCTIONS:
        return json.dumps({"error": f"Outil inconnu : {tool_name}"})

    try:
        result = TOOL_FUNCTIONS[tool_name](tool_input)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"Erreur lors de l'appel de l'outil {tool_name}: {e}")
        return json.dumps({"error": str(e)})


def process_message(user_message: str, conversation_history: list = None) -> str:
    """
    Traite un message utilisateur via Mistral avec Tool Use.

    Flux :
    1. Envoyer le message à Mistral avec la liste des outils disponibles.
    2. Mistral analyse et peut demander d'appeler un ou plusieurs outils.
    3. Exécuter les outils demandés et retourner les résultats à Mistral.
    4. Mistral formule la réponse finale en français.

    Args:
        user_message: Message de l'utilisateur en langage naturel.
        conversation_history: Historique de la conversation (liste de dicts).

    Returns:
        Réponse de Jeffrey en français.
    """
    if conversation_history is None:
        conversation_history = []

    # Contexte de date/heure actuelle pour aider Mistral à résoudre "demain", "après-demain", etc.
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    system_prompt = (
        "Tu es Jeffrey, un assistant personnel efficace et sympathique. "
        "Tu réponds toujours en français. "
        "Tu aides l'utilisateur à gérer :"
        "1. Ses tâches (Google Tasks)"
        "2. Son calendrier (Google Calendar)"
        "3. Ses emails (Gmail)"
        "Quand l'utilisateur mentionne des dates relatives comme 'demain', 'après-demain', 'la semaine prochaine', "
        f"utilise la date actuelle pour les calculer. Aujourd'hui nous sommes le {now.strftime('%A %d %B %Y à %H:%M')} "
        f"(timezone: {TIMEZONE}). "
        "Sois concis dans tes réponses et confirme toujours les actions effectuées."
        "Pour les emails, tu peux :"
        "- Lister les emails récents"
        "- Rechercher des emails par mot-clé"
        "- Lire le contenu d'un email spécifique"
        "- Marquer des emails comme lus/non lus"
        "Ne jamais partager d'informations sensibles des emails sans demande explicite."
    )

    # Ajouter le message utilisateur à l'historique
    messages = conversation_history + [{"role": "user", "content": user_message}]

    # Appel à l'API Mistral avec outils
    try:
        # Utiliser la bonne méthode pour appeler l'API Mistral
        chat_obj = client.chat
        
        # Utiliser la méthode complete (la bonne méthode pour Mistral)
        if hasattr(chat_obj, 'complete'):
            chat_response = chat_obj.complete(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
            )
        elif hasattr(chat_obj, 'stream'):
            # Utiliser le streaming si complete n'est pas disponible
            chat_response = chat_obj.stream(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
            )
            # Consommer le stream pour obtenir la réponse complète
            full_response = ""
            for chunk in chat_response:
                if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                    if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                        full_response += chunk.choices[0].delta.content
            # Créer un objet réponse similaire
            class StreamResponse:
                def __init__(self, content):
                    self.choices = [type('obj', (object,), {'message': type('obj', (object,), {'content': content, 'tool_calls': None})()})()]
            chat_response = StreamResponse(full_response)
        else:
            raise AttributeError("Aucune méthode complete ou stream disponible sur l'objet chat")
        
        # Vérifier le type de réponse
        if chat_response is None:
            raise ValueError("La réponse de l'API est None")
        
        # Extraire les données de la réponse
        if hasattr(chat_response, 'choices'):
            response = chat_response
        elif hasattr(chat_response, 'data'):
            response = chat_response.data
        elif isinstance(chat_response, dict):
            response = chat_response
        else:
            # Essayer d'accéder aux attributs courants
            response = chat_response
            
    except Exception as e:
        logger.error(f"Erreur API Mistral : {e}")
        logger.error(f"Type d'erreur: {type(e).__name__}")
        return f"Désolé, une erreur s'est produite avec l'API Mistral : {e}"

    # Traiter la réponse
    try:
        logger.debug(f"Type de réponse: {type(response)}")
        logger.debug(f"Attributs de réponse: {dir(response) if hasattr(response, '__dir__') else 'N/A'}")
        
        # Accéder aux choix - peut être response.choices ou response['choices']
        if hasattr(response, 'choices'):
            choices = response.choices
            logger.debug(f"Choices trouvé: {len(choices)} choix")
        elif isinstance(response, dict) and 'choices' in response:
            choices = response['choices']
            logger.debug(f"Choices dict trouvé: {len(choices)} choix")
        else:
            # Essayer d'autres noms courants
            if hasattr(response, 'data'):
                choices = response.data
            elif hasattr(response, 'result'):
                choices = response.result
            elif hasattr(response, 'output'):
                choices = response.output
            else:
                choices = [getattr(response, 'choice', None)]
                logger.debug(f"Aucun choix standard trouvé, utilisation de fallback")
        
        if choices and len(choices) > 0:
            message = choices[0].message if hasattr(choices[0], 'message') else choices[0]
            
            # Vérifier les tool calls
            tool_calls = None
            if hasattr(message, 'tool_calls'):
                tool_calls = message.tool_calls
            elif isinstance(message, dict) and 'tool_calls' in message:
                tool_calls = message['tool_calls']
            
            if tool_calls:
                # Mistral veut appeler des outils
                # Ajouter le message de l'assistant avec les tool_calls
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": tool_calls,
                })
                
                # Exécuter les outils et ajouter les résultats
                tool_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call.function.name if hasattr(tool_call.function, 'name') else tool_call['function']['name']
                    tool_args = tool_call.function.arguments if hasattr(tool_call.function, 'arguments') else tool_call['function']['arguments']
                    
                    if isinstance(tool_args, str):
                        tool_args = json.loads(tool_args)
                    
                    logger.info(f"Mistral appelle l'outil : {tool_name} avec {tool_args}")
                    result = _execute_tool(tool_name, tool_args)
                    
                    # Ajouter le résultat au message pour Mistral
                    messages.append({
                        "role": "tool",
                        "content": result,
                        "tool_call_id": tool_call.id if hasattr(tool_call, 'id') else tool_call.get('id'),
                    })

                # Envoyer les résultats des outils à Mistral pour obtenir la réponse finale
                final_chat_response = chat_obj.complete(
                    model=MODEL,
                    messages=messages,
                )
                
                # Extraire la réponse finale
                if hasattr(final_chat_response, 'choices'):
                    final_choices = final_chat_response.choices
                elif isinstance(final_chat_response, dict) and 'choices' in final_chat_response:
                    final_choices = final_chat_response['choices']
                else:
                    final_choices = [getattr(final_chat_response, 'choice', None)]
                
                if final_choices and len(final_choices) > 0:
                    final_message = final_choices[0].message if hasattr(final_choices[0], 'message') else final_choices[0]
                    final_content = final_message.content if hasattr(final_message, 'content') else final_message.get('content', '')
                    return final_content if final_content else "Désolé, je n'ai pas pu obtenir de réponse."
                else:
                    return "Désolé, je n'ai pas pu obtenir de réponse."
            else:
                # Réponse directe sans appel d'outils
                content = message.content if hasattr(message, 'content') else message.get('content', '')
                return content if content else "Désolé, je n'ai pas compris."
        else:
            return "Désolé, je n'ai pas reçu de réponse valide."
    except Exception as e:
        logger.error(f"Erreur lors du traitement de la réponse Mistral : {e}")
        return f"Désolé, une erreur s'est produite lors du traitement : {e}"
