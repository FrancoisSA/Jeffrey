"""
notes.py — Stockage des notes associées aux weekends (SQLite).

Chaque note est identifiée par la date du samedi du weekend (YYYY-MM-DD).

Utilisation :
    from dashboard.notes import get_all_notes, set_note
"""
import sqlite3
import logging
import os

logger = logging.getLogger(__name__)

# Même base SQLite que le journal
_DB_PATH = os.path.join(os.path.dirname(__file__), "journal.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_notes_db():
    """Crée la table des notes de weekend si elle n'existe pas."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS weekend_notes (
                sat_date TEXT PRIMARY KEY,  -- Date du samedi au format YYYY-MM-DD
                note     TEXT NOT NULL DEFAULT ''
            )
        """)
        conn.commit()


def get_all_notes() -> dict:
    """
    Retourne toutes les notes sous forme {sat_date: note}.
    Seules les notes non vides sont retournées.
    """
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT sat_date, note FROM weekend_notes WHERE note != ''"
            ).fetchall()
        return {row["sat_date"]: row["note"] for row in rows}
    except Exception as e:
        logger.error(f"Erreur lecture notes weekends : {e}")
        return {}


def set_note(sat_date: str, note: str):
    """
    Enregistre ou met à jour la note d'un weekend.

    Args:
        sat_date: Date du samedi au format YYYY-MM-DD.
        note:     Contenu de la note (vide = suppression logique).
    """
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO weekend_notes (sat_date, note) VALUES (?, ?) "
                "ON CONFLICT(sat_date) DO UPDATE SET note = excluded.note",
                (sat_date, note.strip()),
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Erreur écriture note weekend {sat_date} : {e}")


# Initialiser au chargement du module
init_notes_db()
