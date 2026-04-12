"""
Service Google Gmail.
Fournit les opérations de base sur les emails :
- Lister les emails récents
- Rechercher des emails
- Lire le contenu d'un email
- Marquer comme lu/non lu
"""
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from services.google_auth import get_google_credentials
import base64
from bs4 import BeautifulSoup


def _get_service():
    """Construit le client Gmail."""
    creds = get_google_credentials()
    return build("gmail", "v1", credentials=creds)


def list_emails(max_results: int = 10, days_back: int = 7) -> list[dict]:
    """
    Liste les emails récents.

    Args:
        max_results: Nombre maximum d'emails à retourner.
        days_back: Nombre de jours en arrière à considérer.

    Returns:
        Liste de dicts avec id, subject, from, date, snippet, is_unread.
    """
    service = _get_service()
    
    # Calculer la date de début
    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y/%m/%d")
    query = f"after:{start_date}"
    
    result = service.users().messages().list(
        userId="me",
        maxResults=max_results,
        q=query
    ).execute()

    messages = result.get("messages", [])
    emails = []

    for msg in messages:
        msg_data = service.users().messages().get(
            userId="me",
            id=msg["id"],
            format="metadata",
            metadataHeaders=["Subject", "From", "Date"]
        ).execute()

        headers = msg_data.get("payload", {}).get("headers", {})
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
        date_str = next((h["value"] for h in headers if h["name"] == "Date"), "")

        emails.append({
            "id": msg["id"],
            "subject": subject,
            "from": sender,
            "date": date_str,
            "snippet": msg_data.get("snippet", ""),
            "is_unread": "UNREAD" in msg_data.get("labelIds", [])
        })

    return emails


def search_emails(keyword: str, max_results: int = 10) -> list[dict]:
    """
    Recherche des emails contenant un mot-clé.

    Args:
        keyword: Mot-clé à rechercher dans sujet/contenu.
        max_results: Nombre maximum de résultats.

    Returns:
        Liste des emails correspondants.
    """
    service = _get_service()
    
    result = service.users().messages().list(
        userId="me",
        maxResults=max_results,
        q=keyword
    ).execute()

    messages = result.get("messages", [])
    return [get_email(msg["id"])
            for msg in messages]


def get_email(email_id: str) -> dict:
    """
    Récupère le contenu complet d'un email.

    Args:
        email_id: ID de l'email.

    Returns:
        Dict avec sujet, expéditeur, date, corps (texte et html), pièces jointes.
    """
    service = _get_service()
    
    msg = service.users().messages().get(
        userId="me",
        id=email_id,
        format="full"
    ).execute()

    headers = msg["payload"]["headers"]
    subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)")
    sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
    date_str = next((h["value"] for h in headers if h["name"] == "Date"), "")

    # Extraire le corps du message
    body_text = ""
    body_html = ""
    
    if "parts" in msg["payload"]:
        for part in msg["payload"]["parts"]:
            if part["mimeType"] == "text/plain":
                body_text = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
            elif part["mimeType"] == "text/html":
                body_html = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                # Convertir HTML en texte lisible
                body_text = BeautifulSoup(body_html, "html.parser").get_text()

    # Vérifier les pièces jointes
    attachments = []
    if "parts" in msg["payload"]:
        for part in msg["payload"]["parts"]:
            if "filename" in part and part["filename"]:
                attachments.append({
                    "filename": part["filename"],
                    "mime_type": part["mimeType"],
                    "size": part["body"]["size"] if "size" in part["body"] else 0
                })

    return {
        "id": email_id,
        "subject": subject,
        "from": sender,
        "date": date_str,
        "body_text": body_text,
        "body_html": body_html,
        "attachments": attachments,
        "is_unread": "UNREAD" in msg["labelIds"]
    }


def mark_as_read(email_id: str) -> bool:
    """
    Marque un email comme lu.

    Args:
        email_id: ID de l'email.

    Returns:
        True si succès.
    """
    service = _get_service()
    service.users().messages().modify(
        userId="me",
        id=email_id,
        body={"removeLabelIds": ["UNREAD"]}
    ).execute()
    return True


def mark_as_unread(email_id: str) -> bool:
    """
    Marque un email comme non lu.

    Args:
        email_id: ID de l'email.

    Returns:
        True si succès.
    """
    service = _get_service()
    service.users().messages().modify(
        userId="me",
        id=email_id,
        body={"addLabelIds": ["UNREAD"]}
    ).execute()
    return True
