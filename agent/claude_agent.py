"""
Agent Claude (Anthropic) avec Tool Use.
Reçoit les messages Telegram en langage naturel (français),
analyse l'intention et appelle les outils Google Tasks / Calendar appropriés.

Les outils disponibles sont déclarés sous forme de JSON Schema et envoyés à Claude
qui décide quel outil appeler et avec quels arguments.
"""
import json
import logging
from datetime import datetime

import anthropic
import pytz

from config import ANTHROPIC_API_KEY, TIMEZONE
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

logger = logging.getLogger(__name__)

# Client Anthropic
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Modèle à utiliser
MODEL = "claude-sonnet-4-6"

# ---------------------------------------------------------
# Définition des outils exposés à Claude
# ---------------------------------------------------------
TOOLS = [
    {
        "name": "list_tasks",
        "description": "Liste les tâches Google Tasks à faire. Utiliser pour afficher les tâches en cours.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Nombre maximum de tâches à retourner (défaut: 20).",
                    "default": 20,
                },
                "show_completed": {
                    "type": "boolean",
                    "description": "Inclure les tâches complétées (défaut: false).",
                    "default": False,
                },
            },
            "required": [],
        },
    },
    {
        "name": "add_task",
        "description": "Ajoute une nouvelle tâche dans Google Tasks.",
        "input_schema": {
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
    {
        "name": "complete_task",
        "description": "Marque une tâche comme complétée/terminée.",
        "input_schema": {
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
    {
        "name": "delete_task",
        "description": "Supprime définitivement une tâche.",
        "input_schema": {
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
    {
        "name": "update_task",
        "description": "Modifie une tâche existante (titre, date, notes).",
        "input_schema": {
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
    {
        "name": "search_tasks",
        "description": "Recherche des tâches par mot-clé dans le titre ou les notes.",
        "input_schema": {
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
    {
        "name": "list_events",
        "description": "Liste les événements Google Calendar à venir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": "Nombre de jours à regarder en avant (défaut: 7).",
                    "default": 7,
                },
                "max_results": {
                    "type": "integer",
                    "description": "Nombre maximum d'événements (défaut: 20).",
                    "default": 20,
                },
            },
            "required": [],
        },
    },
    {
        "name": "add_event",
        "description": "Ajoute un événement dans Google Calendar.",
        "input_schema": {
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
    {
        "name": "update_event",
        "description": "Modifie un événement Google Calendar existant.",
        "input_schema": {
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
    {
        "name": "delete_event",
        "description": "Supprime définitivement un événement du calendrier.",
        "input_schema": {
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
    {
        "name": "search_events",
        "description": "Recherche des événements par mot-clé dans le calendrier.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "Mot-clé à rechercher.",
                },
                "days_ahead": {
                    "type": "integer",
                    "description": "Plage de recherche en jours (défaut: 30).",
                    "default": 30,
                },
            },
            "required": ["keyword"],
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
}


def _execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    Exécute l'outil demandé par Claude et retourne le résultat en JSON.

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
    Traite un message utilisateur via Claude avec Tool Use.

    Flux :
    1. Envoyer le message à Claude avec la liste des outils disponibles.
    2. Claude analyse et peut demander d'appeler un ou plusieurs outils.
    3. Exécuter les outils demandés et retourner les résultats à Claude.
    4. Claude formule la réponse finale en français.

    Args:
        user_message: Message de l'utilisateur en langage naturel.
        conversation_history: Historique de la conversation (liste de dicts).

    Returns:
        Réponse de Jeffrey en français.
    """
    if conversation_history is None:
        conversation_history = []

    # Contexte de date/heure actuelle pour aider Claude à résoudre "demain", "après-demain", etc.
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    system_prompt = (
        "Tu es Jeffrey, un assistant personnel efficace et sympathique. "
        "Tu réponds toujours en français. "
        "Tu aides l'utilisateur à gérer ses tâches (Google Tasks) et son calendrier (Google Calendar). "
        "Quand l'utilisateur mentionne des dates relatives comme 'demain', 'après-demain', 'la semaine prochaine', "
        f"utilise la date actuelle pour les calculer. Aujourd'hui nous sommes le {now.strftime('%A %d %B %Y à %H:%M')} "
        f"(timezone: {TIMEZONE}). "
        "Sois concis dans tes réponses et confirme toujours les actions effectuées."
    )

    # Ajouter le message utilisateur à l'historique
    messages = conversation_history + [{"role": "user", "content": user_message}]

    # Boucle agentique : continuer tant que Claude demande des appels d'outils
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        # Ajouter la réponse de l'assistant à l'historique
        messages.append({"role": "assistant", "content": response.content})

        # Si Claude a terminé sans appeler d'outils → retourner la réponse
        if response.stop_reason == "end_turn":
            # Extraire le texte de la réponse
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return "Je n'ai pas pu traiter votre demande."

        # Si Claude veut appeler des outils
        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    logger.info(f"Claude appelle l'outil : {block.name} avec {block.input}")
                    result = _execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            # Retourner les résultats des outils à Claude
            messages.append({"role": "user", "content": tool_results})

        else:
            # Stop reason inattendu
            logger.warning(f"Stop reason inattendu : {response.stop_reason}")
            break

    return "Une erreur inattendue s'est produite."
