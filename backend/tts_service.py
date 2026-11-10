
import os
import requests
from dotenv import load_dotenv

load_dotenv()

GNANI_API_KEY = os.getenv("GNANI_API_KEY_ID")
GNANI_TTS_VOICE = os.getenv("GNANI_TTS_VOICE", "Avinash")

GNANI_TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"


def generate_speech(text: str, language: str = "te-IN"):

    if not GNANI_API_KEY:
        raise ValueError("Gnani API key is missing")

    headers = {
        "X-API-Key-ID": GNANI_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "text": text,
        "voice": GNANI_TTS_VOICE,
        "model": "timbre-v3.0",
        "language": language,
        "speed": 1.0,
        "audio_config": {
            "sample_rate": 48000,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "wav"
        }
    }

    try:
        response = requests.post(
            GNANI_TTS_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

        response.raise_for_status()

        if not response.content:
            raise RuntimeError("Gnani returned empty audio")

        return response.content

    except requests.HTTPError as error:
        raise RuntimeError(
            f"Gnani TTS error: {error.response.status_code} "
            f"- {error.response.text}"
        )

    except requests.RequestException as error:
        raise RuntimeError(
            f"Gnani TTS connection failed: {error}"
        )
