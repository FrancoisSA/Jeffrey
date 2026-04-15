"""
web.py — Dashboard web de Jeffrey.

Accessible sur http://<raspberry-ip>:8080
Lance avec : python dashboard/web.py

Routes :
  GET  /               → Interface principale (dashboard.html)
  GET  /api/tasks      → Tâches Google Tasks (JSON)
  GET  /api/events     → Événements Google Calendar (JSON)
  GET  /api/journal    → Journal des échanges (JSON, paginé)
  GET  /api/stats      → Métriques résumées (JSON)
"""
import sys
import os
import logging
from datetime import datetime

import pytz
from flask import Flask, jsonify, render_template, request

# Ajouter la racine du projet au path pour importer config et services
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import TIMEZONE
from services.google_tasks import list_tasks, complete_task
from services.google_calendar import list_events
from dashboard.journal import get_recent_exchanges, get_exchange_count
from dashboard.notes import get_all_notes, set_note

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates")


# ---------------------------------------------------------
# Page principale
# ---------------------------------------------------------

@app.route("/")
def index():
    """Affiche le dashboard principal."""
    return render_template("dashboard.html")


@app.route("/journal")
def journal_page():
    """Page dédiée au journal des échanges."""
    return render_template("journal.html")


# ---------------------------------------------------------
# API — Tâches
# ---------------------------------------------------------

@app.route("/api/tasks")
def api_tasks():
    """
    Retourne les tâches Google Tasks, classées par statut.

    Query params :
      max_results (int, défaut 50)
    """
    max_results = request.args.get("max_results", default=50, type=int)
    try:
        tasks = list_tasks(max_results=max_results, show_completed=False)
    except Exception as e:
        logger.error(f"Erreur Google Tasks : {e}")
        return jsonify({"error": str(e)}), 500

    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).date()

    # Classifier chaque tâche
    for task in tasks:
        due_str = task.get("due")
        if not due_str:
            task["status_label"] = "upcoming"
            continue
        try:
            due_dt = datetime.fromisoformat(due_str.replace("Z", "+00:00")).astimezone(tz)
            due_date = due_dt.date()
            if due_date < today:
                task["status_label"] = "overdue"
            elif due_date == today:
                task["status_label"] = "today"
            else:
                task["status_label"] = "upcoming"
            # Formater la date pour l'affichage
            task["due_display"] = due_dt.strftime("%d/%m/%Y")
        except Exception:
            task["status_label"] = "upcoming"

    return jsonify(tasks)


# ---------------------------------------------------------
# API — Compléter une tâche
# ---------------------------------------------------------

@app.route("/api/tasks/<task_id>/complete", methods=["POST"])
def api_task_complete(task_id):
    """Marque une tâche comme complétée dans Google Tasks."""
    try:
        result = complete_task(task_id)
        return jsonify({"ok": True, "task": result})
    except Exception as e:
        logger.error(f"Erreur complete_task {task_id} : {e}")
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------
# API — Événements
# ---------------------------------------------------------

@app.route("/api/events")
def api_events():
    """
    Retourne les événements Google Calendar des N prochains jours.

    Query params :
      days_ahead   (int, défaut 30)
      max_results  (int, défaut 50)
    """
    days_ahead  = request.args.get("days_ahead",  default=30, type=int)
    max_results = request.args.get("max_results", default=50, type=int)
    try:
        events = list_events(days_ahead=days_ahead, max_results=max_results)
    except Exception as e:
        logger.error(f"Erreur Google Calendar : {e}")
        return jsonify({"error": str(e)}), 500

    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).date()

    # Enrichir chaque événement avec des champs d'affichage
    for event in events:
        start_str = event.get("start", "")
        if "T" in start_str:
            try:
                start_dt = datetime.fromisoformat(start_str).astimezone(tz)
                event["date_display"] = start_dt.strftime("%A %d %B")
                event["time_display"] = start_dt.strftime("%H:%M")
                event["is_today"] = (start_dt.date() == today)
                event["date_key"] = start_dt.strftime("%Y-%m-%d")
            except Exception:
                event["date_display"] = start_str[:10]
                event["time_display"] = ""
                event["is_today"] = False
                event["date_key"] = start_str[:10]
        else:
            # Événement journée entière
            event["date_display"] = start_str
            event["time_display"] = "Journée"
            event["is_today"] = (start_str == str(today))
            event["date_key"] = start_str

    return jsonify(events)


# ---------------------------------------------------------
# API — Journal
# ---------------------------------------------------------

@app.route("/api/journal")
def api_journal():
    """
    Retourne les échanges du journal (paginés).

    Query params :
      limit   (int, défaut 30)
      offset  (int, défaut 0)
    """
    limit  = request.args.get("limit",  default=30, type=int)
    offset = request.args.get("offset", default=0,  type=int)
    try:
        exchanges = get_recent_exchanges(limit=limit, offset=offset)
        total     = get_exchange_count()
    except Exception as e:
        logger.error(f"Erreur lecture journal : {e}")
        return jsonify({"error": str(e)}), 500

    # Formater le timestamp pour l'affichage (UTC → timezone locale)
    tz = pytz.timezone(TIMEZONE)
    for ex in exchanges:
        try:
            dt = datetime.fromisoformat(ex["timestamp"]).replace(tzinfo=pytz.utc).astimezone(tz)
            ex["timestamp_display"] = dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            ex["timestamp_display"] = ex.get("timestamp", "")

    return jsonify({"exchanges": exchanges, "total": total, "limit": limit, "offset": offset})


# ---------------------------------------------------------
# API — Stats (métriques pour les cards du haut)
# ---------------------------------------------------------

@app.route("/api/stats")
def api_stats():
    """Retourne les métriques résumées : compteurs de tâches et d'événements."""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today = now.date()

    # --- Tâches ---
    overdue_count  = 0
    today_count    = 0
    upcoming_count = 0

    try:
        tasks = list_tasks(max_results=100, show_completed=False)
        for task in tasks:
            due_str = task.get("due")
            if not due_str:
                upcoming_count += 1
                continue
            try:
                due_date = datetime.fromisoformat(due_str.replace("Z", "+00:00")).astimezone(tz).date()
                if due_date < today:
                    overdue_count += 1
                elif due_date == today:
                    today_count += 1
                else:
                    upcoming_count += 1
            except Exception:
                upcoming_count += 1
        tasks_error = None
    except Exception as e:
        tasks_error = str(e)

    # --- Événements du jour ---
    today_events_count = 0
    try:
        events = list_events(days_ahead=1, max_results=20)
        for event in events:
            start_str = event.get("start", "")
            if "T" in start_str:
                try:
                    start_date = datetime.fromisoformat(start_str).astimezone(tz).date()
                    if start_date == today:
                        today_events_count += 1
                except Exception:
                    pass
            elif start_str == str(today):
                today_events_count += 1
        events_error = None
    except Exception as e:
        events_error = str(e)

    return jsonify({
        "tasks": {
            "overdue":  overdue_count,
            "today":    today_count,
            "upcoming": upcoming_count,
            "error":    tasks_error,
        },
        "events": {
            "today": today_events_count,
            "error": events_error,
        },
        "journal": {
            "total": get_exchange_count(),
        },
        "updated_at": now.strftime("%d/%m/%Y %H:%M:%S"),
    })


# ---------------------------------------------------------
# API — Notes de weekends
# ---------------------------------------------------------

@app.route("/api/weekend-notes")
def api_weekend_notes_get():
    """Retourne toutes les notes de weekends sous forme {sat_date: note}."""
    return jsonify(get_all_notes())


@app.route("/api/weekend-notes/<sat_date>", methods=["PUT"])
def api_weekend_notes_put(sat_date):
    """
    Enregistre ou met à jour la note d'un weekend.

    Body JSON : {"note": "..."}
    sat_date  : date du samedi au format YYYY-MM-DD.
    """
    data = request.get_json() or {}
    note = str(data.get("note", ""))
    set_note(sat_date, note)
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", 8080))
    logger.info(f"Dashboard Jeffrey démarré sur http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
