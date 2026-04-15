#!/bin/bash
# restart.sh — Relance les services Jeffrey sur FSA-PI5
#
# Usage :
#   ./restart.sh              # Relance bot + dashboard
#   ./restart.sh bot          # Relance uniquement le bot (systemd)
#   ./restart.sh dashboard    # Relance uniquement le dashboard Flask

set -e

TARGET="fsalazar@FSA-PI5.local"
SSH="ssh -i ~/.ssh/id_ed25519 $TARGET"
REMOTE="/home/fsalazar/jeffrey"

# ── Vérification connectivité ────────────────────────────────────────────
if ! ssh -i ~/.ssh/id_ed25519 -o ConnectTimeout=5 "$TARGET" "echo ok" > /dev/null 2>&1; then
    echo "ERREUR : impossible de joindre $TARGET"
    exit 1
fi

MODE="${1:-all}"

# ── Relance du bot (service systemd jeffrey) ─────────────────────────────
restart_bot() {
    echo "→ Relance du bot Telegram (jeffrey.service)..."
    $SSH "sudo systemctl restart jeffrey"
    sleep 2
    $SSH "sudo systemctl status jeffrey --no-pager -l | head -20"
    echo "✓ Bot relancé."
}

# ── Relance du dashboard Flask ───────────────────────────────────────────
restart_dashboard() {
    echo "→ Relance du dashboard Flask..."
    $SSH "pkill -f 'dashboard/web.py' || true"
    sleep 1
    $SSH "cd $REMOTE && nohup venv/bin/python dashboard/web.py > dashboard.log 2>&1 &"
    sleep 2
    PID=$($SSH "pgrep -f 'dashboard/web.py'" 2>/dev/null || echo "introuvable")
    echo "✓ Dashboard relancé (PID: $PID) — http://FSA-PI5.local:8080"
}

# ── Dispatch ─────────────────────────────────────────────────────────────
case "$MODE" in
    bot)       restart_bot ;;
    dashboard) restart_dashboard ;;
    all)       restart_bot; echo ""; restart_dashboard ;;
    *)
        echo "Usage : $0 [bot|dashboard|all]"
        exit 1
        ;;
esac

echo ""
echo "=== Terminé ==="
