"""
Dashboard Streamlit - Interface de monitoring Jeffrey.
Affiche les tâches Google Tasks et les événements Google Calendar
dans une interface web locale.

Lancement : streamlit run dashboard/app.py
"""
import sys
import os
from datetime import datetime

import pytz
import streamlit as st

# Ajouter le répertoire parent au path pour importer les services
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.google_tasks import list_tasks
from services.google_calendar import list_events
from config import TIMEZONE

# ---------------------------------------------------------
# Configuration de la page Streamlit
# ---------------------------------------------------------
st.set_page_config(
    page_title="Jeffrey - Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------
# CSS personnalisé pour un affichage propre
# ---------------------------------------------------------
st.markdown("""
<style>
    .stMetric { background-color: #f0f2f6; border-radius: 8px; padding: 10px; }
    .task-overdue { color: #d32f2f; font-weight: bold; }
    .task-today { color: #f57c00; font-weight: bold; }
    .task-normal { color: #388e3c; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# En-tête
# ---------------------------------------------------------
tz = pytz.timezone(TIMEZONE)
now = datetime.now(tz)

st.title("🤖 Jeffrey — Dashboard")
st.caption(f"Dernière mise à jour : {now.strftime('%d/%m/%Y à %H:%M:%S')}")

# Bouton de rafraîchissement
if st.button("🔄 Rafraîchir"):
    st.rerun()

st.divider()

# ---------------------------------------------------------
# Chargement des données avec cache (TTL 60 secondes)
# ---------------------------------------------------------
@st.cache_data(ttl=60)
def load_tasks():
    """Charge les tâches depuis Google Tasks (avec cache 60s)."""
    return list_tasks(max_results=50, show_completed=False)


@st.cache_data(ttl=60)
def load_events():
    """Charge les événements depuis Google Calendar (avec cache 60s)."""
    return list_events(days_ahead=30, max_results=50)


# Chargement avec gestion d'erreur
try:
    tasks = load_tasks()
    tasks_error = None
except Exception as e:
    tasks = []
    tasks_error = str(e)

try:
    events = load_events()
    events_error = None
except Exception as e:
    events = []
    events_error = str(e)

# ---------------------------------------------------------
# Métriques résumées en haut de page
# ---------------------------------------------------------
today = now.date()

# Classifier les tâches
overdue_tasks = []
today_tasks = []
upcoming_tasks = []

for task in tasks:
    due_str = task.get("due")
    if not due_str:
        upcoming_tasks.append(task)
        continue
    try:
        due_dt = datetime.fromisoformat(due_str.replace("Z", "+00:00")).astimezone(tz)
        due_date = due_dt.date()
        if due_date < today:
            overdue_tasks.append(task)
        elif due_date == today:
            today_tasks.append(task)
        else:
            upcoming_tasks.append(task)
    except Exception:
        upcoming_tasks.append(task)

# Événements du jour
today_events = []
for event in events:
    start_str = event.get("start", "")
    if "T" in start_str:
        try:
            start_dt = datetime.fromisoformat(start_str).astimezone(tz)
            if start_dt.date() == today:
                today_events.append(event)
        except Exception:
            pass

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🔴 Tâches en retard", len(overdue_tasks))
with col2:
    st.metric("🟡 Tâches du jour", len(today_tasks))
with col3:
    st.metric("🟢 Tâches à venir", len(upcoming_tasks))
with col4:
    st.metric("📅 Événements aujourd'hui", len(today_events))

st.divider()

# ---------------------------------------------------------
# Colonne gauche : Tâches | Colonne droite : Calendrier
# ---------------------------------------------------------
col_tasks, col_events = st.columns(2)

# ----- TÂCHES -----
with col_tasks:
    st.subheader("📋 Tâches Google Tasks")

    if tasks_error:
        st.error(f"Erreur de connexion à Google Tasks : {tasks_error}")
    elif not tasks:
        st.success("Aucune tâche en cours ! 🎉")
    else:
        # Tâches en retard
        if overdue_tasks:
            st.markdown("**🔴 En retard**")
            for task in overdue_tasks:
                due_str = task.get("due", "")
                due_display = due_str[:10] if due_str else ""
                with st.expander(f"⚠️ {task['title']} — {due_display}", expanded=True):
                    if task.get("notes"):
                        st.markdown(f"*{task['notes']}*")
                    st.caption(f"ID : `{task['id']}`")

        # Tâches du jour
        if today_tasks:
            st.markdown("**🟡 Aujourd'hui**")
            for task in today_tasks:
                with st.expander(f"📌 {task['title']}", expanded=True):
                    if task.get("notes"):
                        st.markdown(f"*{task['notes']}*")
                    st.caption(f"ID : `{task['id']}`")

        # Tâches à venir
        if upcoming_tasks:
            st.markdown("**🟢 À venir / Sans date**")
            for task in upcoming_tasks:
                due_str = task.get("due", "")
                due_display = f" — {due_str[:10]}" if due_str else ""
                with st.expander(f"✅ {task['title']}{due_display}"):
                    if task.get("notes"):
                        st.markdown(f"*{task['notes']}*")
                    st.caption(f"ID : `{task['id']}`")

# ----- ÉVÉNEMENTS -----
with col_events:
    st.subheader("📅 Agenda Google Calendar (30 jours)")

    if events_error:
        st.error(f"Erreur de connexion à Google Calendar : {events_error}")
    elif not events:
        st.info("Aucun événement dans les 30 prochains jours.")
    else:
        # Grouper les événements par date
        from collections import defaultdict
        events_by_date = defaultdict(list)

        for event in events:
            start_str = event.get("start", "")
            if "T" in start_str:
                try:
                    start_dt = datetime.fromisoformat(start_str).astimezone(tz)
                    date_key = start_dt.strftime("%A %d %B %Y")
                    events_by_date[date_key].append((start_dt, event))
                except Exception:
                    events_by_date["Date inconnue"].append((None, event))
            else:
                # Événement journée entière
                events_by_date[start_str].append((None, event))

        # Afficher par date
        for date_label, day_events in events_by_date.items():
            # Mettre en évidence le jour actuel
            if today.strftime("%A %d %B %Y") == date_label:
                st.markdown(f"**📍 {date_label} (Aujourd'hui)**")
            else:
                st.markdown(f"**{date_label}**")

            for start_dt, event in day_events:
                time_str = start_dt.strftime("%H:%M") if start_dt else "Journée"
                title = event.get("summary", "(sans titre)")

                with st.expander(f"🕐 {time_str} — {title}"):
                    if event.get("location"):
                        st.markdown(f"📍 **Lieu :** {event['location']}")
                    if event.get("description"):
                        st.markdown(f"📝 {event['description']}")
                    st.caption(f"ID : `{event['id']}`")

# ---------------------------------------------------------
# Pied de page
# ---------------------------------------------------------
st.divider()
st.caption("Jeffrey v1.0 — Assistant personnel sur Raspberry Pi | Données issues de Google Tasks & Calendar")
