"""
Service Google Tasks.
Fournit les opérations CRUD sur les tâches :
- Lister les listes de tâches
- Ajouter / modifier / supprimer / compléter des tâches
- Rechercher des tâches par mot-clé
"""
from datetime import datetime
from googleapiclient.discovery import build
from services.google_auth import get_google_credentials
import pytz
from config import TIMEZONE


def _get_service():
    """Construit le client Google Tasks."""
    creds = get_google_credentials()
    return build("tasks", "v1", credentials=creds)


def _get_default_tasklist_id(service) -> str:
    """Retourne l'ID de la liste de tâches par défaut (@default)."""
    return "@default"


def list_tasks(max_results: int = 20, show_completed: bool = False) -> list[dict]:
    """
    Liste les tâches de la liste par défaut.

    Args:
        max_results: Nombre maximum de tâches à retourner.
        show_completed: Inclure les tâches déjà complétées.

    Returns:
        Liste de dicts avec id, title, due, notes, status.
    """
    service = _get_service()
    result = service.tasks().list(
        tasklist=_get_default_tasklist_id(service),
        maxResults=max_results,
        showCompleted=show_completed,
        showHidden=show_completed,
    ).execute()

    tasks = result.get("items", [])
    return [
        {
            "id": t.get("id"),
            "title": t.get("title", ""),
            "due": t.get("due"),       # Format RFC 3339
            "notes": t.get("notes", ""),
            "status": t.get("status", "needsAction"),
        }
        for t in tasks
    ]


def add_task(title: str, due: str = None, notes: str = None) -> dict:
    """
    Ajoute une nouvelle tâche.

    Args:
        title: Titre de la tâche.
        due: Date d'échéance au format ISO 8601 (ex: "2024-04-15T12:00:00").
        notes: Notes additionnelles.

    Returns:
        La tâche créée.
    """
    service = _get_service()
    task_body = {"title": title}

    if due:
        # Google Tasks attend le format RFC 3339 avec suffixe Z
        tz = pytz.timezone(TIMEZONE)
        dt = datetime.fromisoformat(due)
        if dt.tzinfo is None:
            dt = tz.localize(dt)
        task_body["due"] = dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    if notes:
        task_body["notes"] = notes

    result = service.tasks().insert(
        tasklist=_get_default_tasklist_id(service),
        body=task_body,
    ).execute()

    return {"id": result["id"], "title": result.get("title"), "due": result.get("due")}


def complete_task(task_id: str) -> dict:
    """
    Marque une tâche comme complétée.

    Args:
        task_id: L'ID de la tâche à compléter.

    Returns:
        La tâche mise à jour.
    """
    service = _get_service()
    tasklist_id = _get_default_tasklist_id(service)

    # Récupérer la tâche pour ne modifier que le statut
    task = service.tasks().get(tasklist=tasklist_id, task=task_id).execute()
    task["status"] = "completed"

    result = service.tasks().update(
        tasklist=tasklist_id,
        task=task_id,
        body=task,
    ).execute()

    return {"id": result["id"], "title": result.get("title"), "status": result.get("status")}


def delete_task(task_id: str) -> bool:
    """
    Supprime une tâche.

    Args:
        task_id: L'ID de la tâche à supprimer.

    Returns:
        True si la suppression a réussi.
    """
    service = _get_service()
    service.tasks().delete(
        tasklist=_get_default_tasklist_id(service),
        task=task_id,
    ).execute()
    return True


def update_task(task_id: str, title: str = None, due: str = None, notes: str = None) -> dict:
    """
    Modifie une tâche existante.

    Args:
        task_id: L'ID de la tâche à modifier.
        title: Nouveau titre (optionnel).
        due: Nouvelle date d'échéance ISO 8601 (optionnel).
        notes: Nouvelles notes (optionnel).

    Returns:
        La tâche mise à jour.
    """
    service = _get_service()
    tasklist_id = _get_default_tasklist_id(service)

    # Récupérer l'état actuel de la tâche
    task = service.tasks().get(tasklist=tasklist_id, task=task_id).execute()

    if title:
        task["title"] = title
    if due:
        tz = pytz.timezone(TIMEZONE)
        dt = datetime.fromisoformat(due)
        if dt.tzinfo is None:
            dt = tz.localize(dt)
        task["due"] = dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    if notes is not None:
        task["notes"] = notes

    result = service.tasks().update(
        tasklist=tasklist_id,
        task=task_id,
        body=task,
    ).execute()

    return {"id": result["id"], "title": result.get("title"), "due": result.get("due")}


def search_tasks(keyword: str) -> list[dict]:
    """
    Recherche des tâches contenant un mot-clé dans le titre ou les notes.

    Args:
        keyword: Mot-clé à rechercher (insensible à la casse).

    Returns:
        Liste des tâches correspondantes.
    """
    all_tasks = list_tasks(max_results=100, show_completed=False)
    keyword_lower = keyword.lower()

    return [
        t for t in all_tasks
        if keyword_lower in t["title"].lower() or keyword_lower in (t["notes"] or "").lower()
    ]
