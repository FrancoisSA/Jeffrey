#!/bin/bash
# Script de déploiement Jeffrey → Raspberry Pi FSA-PI5
# Usage : ./deploy.sh
#
# Prérequis :
#   - Le Pi est accessible sur le réseau (FSA-PI5.local)
#   - La clé SSH ~/.ssh/id_ed25519 est autorisée sur fsalazar@FSA-PI5.local
#   - Le fichier .env et credentials.json/token.json existent déjà sur le Pi

set -e

TARGET="fsalazar@FSA-PI5.local"
REMOTE_DIR="/home/fsalazar/jeffrey"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_FILE="jeffrey.service"

echo "=== Déploiement Jeffrey → FSA-PI5 ==="

# Vérification de la connectivité
echo "[0/5] Vérification de la connexion SSH..."
if ! ssh -o ConnectTimeout=5 "$TARGET" "echo OK" > /dev/null 2>&1; then
  echo "ERREUR : Impossible de joindre $TARGET"
  echo "Vérifiez que le Raspberry Pi est démarré et accessible."
  exit 1
fi

# Étape 1 : Copier les fichiers source via rsync
# Exclusions : venv, __pycache__, fichiers sensibles (.env, token.json, credentials.json),
# logs, et fichiers inutiles au runtime
echo "[1/5] Copie des fichiers (rsync)..."
rsync -av --delete \
  --exclude "venv/" \
  --exclude "venv_local/" \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  --exclude ".env" \
  --exclude "token.json" \
  --exclude "credentials.json" \
  --exclude "jeffrey.log" \
  --exclude ".git/" \
  --exclude "*.egg-info/" \
  "$LOCAL_DIR/" "$TARGET:$REMOTE_DIR/"

# Étape 2 : Installer/mettre à jour le fichier service systemd
echo "[2/5] Installation du service systemd..."
ssh "$TARGET" "
  sudo cp $REMOTE_DIR/$SERVICE_FILE /etc/systemd/system/$SERVICE_FILE && \
  sudo systemctl daemon-reload && \
  sudo systemctl enable jeffrey
"

# Étape 3 : Installer les dépendances Python dans le venv
echo "[3/5] Installation des dépendances Python..."
ssh "$TARGET" "
  cd $REMOTE_DIR && \
  [ -d venv ] || python3 -m venv venv && \
  venv/bin/pip install -q --upgrade pip && \
  venv/bin/pip install -q -r requirements.txt
"

# Étape 4 : Redémarrer le service
echo "[4/5] Redémarrage du service jeffrey..."
ssh "$TARGET" "sudo systemctl restart jeffrey"
echo "Service relancé."

# Étape 5 : Vérification et logs
echo "[5/5] Statut et logs..."
ssh "$TARGET" "sudo systemctl status jeffrey --no-pager -l"
echo ""
echo "--- Derniers logs ---"
ssh "$TARGET" "sudo journalctl -u jeffrey -n 20 --no-pager"

echo ""
echo "=== Déploiement terminé ! ==="
