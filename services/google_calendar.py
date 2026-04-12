"""
Service Google Calendar.
Fournit les opérations CRUD sur les événements du calendrier principal :
- Lister les événements à venir
- Ajouter / modifier / supprimer des événements
- Rechercher des événements par mot-clé
"""
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from services.google_auth import get_google_credentials
import pytz
from config import TIMEZONE


def _get_service():
    """Construit le client Google Calendar."""
    creds = get_google_credentials()
    return build("calendar", "v3", credentials=creds)


def _localize(dt_str: str) -> str:
    """
    Convertit une chaîne ISO 8601 en datetime localisé au bon fuseau horaire.
    Retourne une chaîne RFC 3339 pour l'API Google.
    """
    tz = pytz.timezone(TIMEZONE)
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = tz.localize(dt)
    return dt.isoformat()


def list_events(days_ahead: int = 7, max_results: int = 20) -> list[dict]:
    """
    Liste les événements des N prochains jours.

    Args:
        days_ahead: Nombre de jours à regarder en avant.
        max_results: Nombre maximum d'événements à retourner.

    Returns:
        Liste de dicts avec id, summary, start, end, description, location.
    """
    service = _get_service()
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    time_max = now + timedelta(days=days_ahead)

    result = service.events().list(
        calendarId="primary",
        timeMin=now.isoformat(),
        timeMax=time_max.isoformat(),
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = result.get("items", [])
    return [_format_event(e) for e in events]


def get_upcoming_events(minutes_ahead: int = 20) -> list[dict]:
    """
    Retourne les événements qui commencent dans les N prochaines minutes.
    Utilisé par le scheduler de rappels.

    Args:
        minutes_ahead: Fenêtre de temps en minutes.

    Returns:
        Liste des événements imminents.
    """
    service = _get_service()
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    time_max = now + timedelta(minutes=minutes_ahead)

    result = service.events().list(
        calendarId="primary",
        timeMin=now.isoformat(),
        timeMax=time_max.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    return [_format_event(e) for e in result.get("items", [])]


def add_event(
    summary: str,
    start: str,
    end: str = None,
    description: str = None,
    location: str = None,
) -> dict:
    """
    Crée un nouvel événement dans le calendrier.

    Args:
        summary: Titre de l'événement.
        start: Datetime de début au format ISO 8601.
        end: Datetime de fin (défaut: 1 heure après le début).
        description: Description / notes de l'événement.
        location: Lieu de l'événement.

    Returns:
        L'événement créé (id, summary, start, end).
    """
    service = _get_service()

    start_dt = datetime.fromisoformat(start)
    if end:
        end_dt = datetime.fromisoformat(end)
    else:
        # Par défaut, durée d'1 heure
        end_dt = start_dt + timedelta(hours=1)

    event_body = {
        "summary": summary,
        "start": {"dateTime": _localize(start), "timeZone": TIMEZONE},
        "end": {"dateTime": _localize(str(end_dt)), "timeZone": TIMEZONE},
    }

    if description:
        event_body["description"] = description
    if location:
        event_body["location"] = location

    result = service.events().insert(calendarId="primary", body=event_body).execute()
    return _format_event(result)


def update_event(
    event_id: str,
    summary: str = None,
    start: str = None,
    end: str = None,
    description: str = None,
    location: str = None,
) -> dict:
    """
    Modifie un événement existant.

    Args:
        event_id: L'ID Google de l'événement.
        summary: Nouveau titre (optionnel).
        start: Nouveau début ISO 8601 (optionnel).
        end: Nouvelle fin ISO 8601 (optionnel).
        description: Nouvelle description (optionnel).
        location: Nouveau lieu (optionnel).

    Returns:
        L'événement mis à jour.
    """
    service = _get_service()

    # Récupérer l'état actuel
    event = service.events().get(calendarId="primary", eventId=event_id).execute()

    if summary:
        event["summary"] = summary
    if start:
        event["start"] = {"dateTime": _localize(start), "timeZone": TIMEZONE}
    if end:
        event["end"] = {"dateTime": _localize(end), "timeZone": TIMEZONE}
    if description is not None:
        event["description"] = description
    if location is not None:
        event["location"] = location

    result = service.events().update(
        calendarId="primary", eventId=event_id, body=event
    ).execute()
    return _format_event(result)


def delete_event(event_id: str) -> bool:
    """
    Supprime un événement du calendrier.

    Args:
        event_id: L'ID Google de l'événement.

    Returns:
        True si la suppression a réussi.
    """
    service = _get_service()
    service.events().delete(calendarId="primary", eventId=event_id).execute()
    return True


def search_events(keyword: str, days_ahead: int = 30) -> list[dict]:
    """
    Recherche des événements contenant un mot-clé dans le titre ou la description.

    Args:
        keyword: Mot-clé à rechercher.
        days_ahead: Plage de recherche en jours.

    Returns:
        Liste des événements correspondants.
    """
    service = _get_service()
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    time_max = now + timedelta(days=days_ahead)

    result = service.events().list(
        calendarId="primary",
        q=keyword,                        # Recherche native de l'API Google
        timeMin=now.isoformat(),
        timeMax=time_max.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    return [_format_event(e) for e in result.get("items", [])]


def _format_event(event: dict) -> dict:
    """Normalise un événement Google Calendar en dict simple."""
    start = event.get("start", {})
    end = event.get("end", {})
    return {
        "id": event.get("id"),
        "summary": event.get("summary", "(sans titre)"),
        "start": start.get("dateTime", start.get("date")),
        "end": end.get("dateTime", end.get("date")),
        "description": event.get("description", ""),
        "location": event.get("location", ""),
    }
