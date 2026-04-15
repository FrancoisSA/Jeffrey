# Jeffrey — Manuel utilisateur v1.1
Date : 2026-04-15

---

## Présentation

Jeffrey est un assistant personnel composé de deux services distincts :

- **Bot Telegram** (`main.py`) — répond aux messages, gère les rappels, transcrit les vocaux
- **Dashboard web** (`dashboard/web.py`) — interface de suivi accessible sur http://FSA-PI5.local:8080

Les deux tournent sur le **Raspberry Pi FSA-PI5** et communiquent avec Google Tasks et Google Calendar.

---

## Architecture

```
prj-jeffrey/
├── main.py                  # Point d'entrée du bot Telegram
├── config.py                # Variables d'environnement
├── bot/
│   └── telegram_bot.py      # Handlers Telegram
├── services/
│   ├── google_tasks.py      # CRUD Google Tasks
│   ├── google_calendar.py   # Lecture Google Calendar
│   ├── google_auth.py       # Authentification OAuth2
│   └── reminder.py          # Scheduler de rappels
├── agent/
│   └── claude_agent.py      # Agent IA (Claude)
├── dashboard/
│   ├── web.py               # Serveur Flask du dashboard
│   ├── journal.py           # Journal des échanges
│   ├── notes.py             # Notes weekends
│   └── templates/           # HTML (base.html, dashboard.html, journal.html)
├── restart.sh               # Script de relance des services
└── deploy.sh                # Script de déploiement local → Pi
```

---

## Démarrage / Arrêt

### Via le script de relance (recommandé)

```bash
./restart.sh          # Relance bot + dashboard
./restart.sh bot      # Relance uniquement le bot
./restart.sh dashboard  # Relance uniquement le dashboard
```

### Manuellement sur le Pi

```bash
ssh -i ~/.ssh/id_ed25519 fsalazar@FSA-PI5.local

# Bot Telegram (service systemd)
sudo systemctl restart jeffrey
sudo journalctl -u jeffrey -f

# Dashboard Flask
pkill -f "dashboard/web.py"
cd /home/fsalazar/jeffrey
nohup venv/bin/python dashboard/web.py > dashboard.log 2>&1 &
```

---

## Dashboard (v1.1)

Accessible sur **http://FSA-PI5.local:8080**

### Fonctionnalités

| Section | Description |
|---|---|
| Cards métriques | Compteurs : tâches en retard, du jour, à venir, RDV aujourd'hui |
| Tâches | Liste Google Tasks classée par urgence |
| ✓ Marquer comme fait | Bouton sur chaque tâche → complète dans Google Tasks et disparaît |
| Agenda | Événements Google Calendar des 30 prochains jours |
| Weekends | Planning des 12 prochains mois avec notes éditables |
| Journal | Historique des échanges Telegram |

### Interface
- **Mode sombre** activé par défaut
- Rafraîchissement automatique toutes les 60 secondes
- Bouton ↺ Rafraîchir pour mise à jour immédiate

---

## Bot Telegram

### Commandes disponibles

| Commande | Action |
|---|---|
| Message texte | Traité par l'agent Claude |
| Message vocal | Transcrit via Whisper, puis traité |
| "ajoute tâche X" | Crée une tâche dans Google Tasks |
| "mes tâches" | Liste les tâches en cours |
| "agenda" | Affiche les prochains événements |
| "rappelle-moi X" | Crée un rappel |

---

## Déploiement

```bash
# Depuis le Mac, pousser les modifications vers le Pi :
./deploy.sh
```

Le script effectue : rsync → pip install → restart service → logs.

---

## Variables d'environnement (.env sur le Pi)

| Variable | Description |
|---|---|
| `TELEGRAM_TOKEN` | Token du bot Telegram |
| `TELEGRAM_CHAT_ID` | ID du chat autorisé |
| `MISTRAL_API_KEY` | Clé API Mistral |
| `ANTHROPIC_API_KEY` | Clé API Claude |
| `GOOGLE_CREDENTIALS_FILE` | Chemin vers credentials.json |
| `TIMEZONE` | Fuseau horaire (ex: Europe/Paris) |
| `DASHBOARD_PORT` | Port du dashboard (défaut : 8080) |

---

## Historique des versions

| Version | Date | Changements |
|---|---|---|
| v1.1 | 2026-04-15 | Dashboard mode sombre · Bouton "Marquer comme fait" sur les tâches · Script restart.sh |
| v1.0 | 2026-04-14 | Version initiale — bot Telegram, transcription vocale Whisper, dashboard Flask |
