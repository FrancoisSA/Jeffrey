"""
journal.py — Journal des échanges Jeffrey (SQLite).

Enregistre chaque message reçu (texte ou vocal) et la réponse de Jeffrey.
Interrogeable depuis le dashboard web.

Utilisation :
    from dashboard.journal import log_exchange, get_recent_exchanges
"""
import sqlite3
import time
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# Chemin de la base de données — à côté de ce fichier, dans dashboard/
_DB_PATH = os.path.join(os.path.dirname(__file__), "journal.db")


def _get_conn() -> sqlite3.Connection:
    """Ouvre une connexion SQLite (thread-safe pour lectures multi-thread Flask)."""
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crée la table du journal si elle n'existe pas encore."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS exchanges (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp    TEXT    NOT NULL,
                message_type TEXT    NOT NULL DEFAULT 'text',  -- 'text' ou 'voice'
                user_message TEXT    NOT NULL,
                jeffrey_reply TEXT   NOT NULL,
                duration_ms  INTEGER
            )
        """)
        conn.commit()
    logger.info(f"Journal initialisé : {_DB_PATH}")


def log_exchange(
    user_message: str,
    jeffrey_reply: str,
    message_type: str = "text",
    duration_ms: int = None,
):
    """
    Enregistre un échange dans le journal.

    Args:
        user_message:  Message envoyé par l'utilisateur.
        jeffrey_reply: Réponse générée par Jeffrey.
        message_type:  'text' ou 'voice'.
        duration_ms:   Durée de traitement en ms (optionnel).
    """
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO exchanges (timestamp, message_type, user_message, jeffrey_reply, duration_ms) "
                "VALUES (?, ?, ?, ?, ?)",
                (ts, message_type, user_message, jeffrey_reply, duration_ms),
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement dans le journal : {e}")


def get_recent_exchanges(limit: int = 50, offset: int = 0) -> list[dict]:
    """
    Retourne les échanges les plus récents, du plus récent au plus ancien.

    Args:
        limit:  Nombre maximum d'échanges à retourner.
        offset: Nombre d'échanges à sauter (pagination).

    Returns:
        Liste de dicts avec id, timestamp, message_type, user_message, jeffrey_reply, duration_ms.
    """
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM exchanges ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Erreur lors de la lecture du journal : {e}")
        return []


def get_exchange_count() -> int:
    """Retourne le nombre total d'échanges enregistrés."""
    try:
        with _get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM exchanges").fetchone()
        return row["cnt"] if row else 0
    except Exception:
        return 0


# Initialiser la base au chargement du module
init_db()
