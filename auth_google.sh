#!/bin/bash
# auth_google.sh - Authentification Google OAuth2 en local
# Lance le navigateur pour autoriser l'accès Google, puis copie token.json sur le Pi

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Authentification Google pour Jeffrey ==="

# Créer le venv local si nécessaire
if [ ! -d "venv_local" ]; then
    echo "[1/3] Création du venv local..."
    python3 -m venv venv_local
fi

# Installer les dépendances nécessaires
echo "[2/3] Installation des dépendances..."
venv_local/bin/pip install -q \
    google-auth-oauthlib \
    google-api-python-client \
    google-auth-httplib2 \
    python-dotenv

# Lancer l'auth (ouvre le navigateur)
echo "[3/3] Lancement de l'authentification Google..."
echo "      → Un navigateur va s'ouvrir, connecte-toi et autorise l'accès."
echo ""

venv_local/bin/python - << 'PYEOF'
import sys
sys.path.insert(0, '.')
from services.google_auth import get_google_credentials
creds = get_google_credentials()
print("")
print("✅ Authentification réussie ! token.json généré.")
PYEOF

# Copier token.json sur le Pi
echo ""
echo "Copie de token.json sur FSA-PI5..."
scp -i ~/.ssh/id_ed25519 token.json fsalazar@FSA-PI5.local:/home/fsalazar/jeffrey/token.json
echo "✅ token.json copié sur le Pi."
echo ""
echo "=== Authentification terminée ! Jeffrey est prêt à démarrer. ==="
