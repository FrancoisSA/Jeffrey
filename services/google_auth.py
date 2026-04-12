"""
Authentification Google OAuth2.
Gère le flux d'authentification et le rafraîchissement du token.
Le token est sauvegardé localement pour éviter de se reconnecter à chaque démarrage.
"""
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from config import GOOGLE_CREDENTIALS_FILE, GOOGLE_TOKEN_FILE, GOOGLE_SCOPES


def get_google_credentials() -> Credentials:
    """
    Retourne des credentials Google valides.
    - Si token.json existe et est valide, l'utilise directement.
    - Si le token est expiré, le rafraîchit automatiquement.
    - Si aucun token, lance le flux OAuth2 (nécessite un navigateur au premier lancement).
    """
    creds = None

    # Charger le token existant s'il existe
    if os.path.exists(GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, GOOGLE_SCOPES)

    # Rafraîchir ou relancer l'auth si nécessaire
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_CREDENTIALS_FILE, GOOGLE_SCOPES
            )
            # port=0 choisit un port libre automatiquement
            creds = flow.run_local_server(port=0)

        # Sauvegarder le token pour les prochains démarrages
        with open(GOOGLE_TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return creds
