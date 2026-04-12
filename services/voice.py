"""
Service de transcription vocale.
Utilise faster-whisper (modèle 'base') pour convertir un fichier audio OGG/Opus
(format envoyé par Telegram) en texte.

Le modèle est chargé une seule fois au premier appel (singleton) pour éviter
de le recharger à chaque message (~145MB en RAM).

Prérequis système : ffmpeg installé (sudo apt install ffmpeg)
"""
import logging
import os
import tempfile

logger = logging.getLogger(__name__)

# Modèle Whisper partagé — chargé à la demande, conservé en mémoire
_whisper_model = None

# Modèle à utiliser : "tiny" (~75MB, ~2s), "base" (~145MB, ~4s), "small" (~244MB, ~8s)
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")


def _get_model():
    """
    Retourne le modèle Whisper, en le chargeant si nécessaire (lazy loading).
    Le premier appel déclenche le téléchargement si le modèle n'est pas en cache.
    """
    global _whisper_model
    if _whisper_model is None:
        logger.info(f"Chargement du modèle Whisper '{WHISPER_MODEL}'...")
        try:
            from faster_whisper import WhisperModel
            # int8 : quantification pour réduire l'empreinte mémoire sur CPU
            _whisper_model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
            logger.info(f"Modèle Whisper '{WHISPER_MODEL}' chargé.")
        except ImportError:
            raise RuntimeError(
                "faster-whisper n'est pas installé. "
                "Lancez : pip install faster-whisper"
            )
    return _whisper_model


def transcribe_audio(file_path: str, language: str = "fr") -> str:
    """
    Transcrit un fichier audio en texte.

    Args:
        file_path: Chemin vers le fichier audio (OGG, MP3, WAV, etc.)
        language:  Code langue ISO 639-1 (défaut: "fr").
                   Forcer la langue évite la détection automatique et accélère la transcription.

    Returns:
        Texte transcrit, ou chaîne vide si le fichier est silencieux.

    Raises:
        RuntimeError: Si ffmpeg n'est pas installé ou si la transcription échoue.
    """
    model = _get_model()

    logger.info(f"Transcription de {file_path} (langue: {language})...")
    try:
        segments, info = model.transcribe(
            file_path,
            language=language,
            beam_size=5,           # Précision vs vitesse (5 est le défaut Whisper)
            vad_filter=True,       # Filtre Voice Activity Detection : ignore les silences
            vad_parameters={"min_silence_duration_ms": 500},
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        logger.info(f"Transcription terminée ({info.duration:.1f}s audio) : '{text[:80]}...'")
        return text
    except Exception as e:
        logger.error(f"Erreur de transcription : {e}")
        raise RuntimeError(f"Échec de la transcription audio : {e}") from e


async def download_and_transcribe(voice_file, language: str = "fr") -> str:
    """
    Télécharge un fichier vocal Telegram et le transcrit.

    Args:
        voice_file: Objet telegram.File (obtenu via await bot.get_file(file_id)).
        language:   Code langue pour la transcription.

    Returns:
        Texte transcrit.
    """
    # Utiliser un fichier temporaire qui sera supprimé automatiquement après usage
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Télécharger le fichier OGG depuis les serveurs Telegram
        await voice_file.download_to_drive(tmp_path)
        logger.info(f"Fichier vocal téléchargé : {tmp_path}")

        # Transcrire
        return transcribe_audio(tmp_path, language=language)
    finally:
        # Toujours supprimer le fichier temporaire, même en cas d'erreur
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
