import os
import requests

from dotenv import load_dotenv

load_dotenv()

GNANI_API_KEY = os.getenv("GNANI_API_KEY_ID")

GNANI_STT_URL = "https://api.vachana.ai/stt/v3"


def transcribe_audio(audio_file):

    if not GNANI_API_KEY:
        raise ValueError("Gnani API key is missing")

    headers = {
        "X-API-Key-ID": GNANI_API_KEY
    }

    files = {
        "audio_file": (
            audio_file.filename,
            audio_file.file,
            audio_file.content_type
        )
    }

    data = {
    "language_code": "indic-auto",
    "multi_lang_codes": "te-IN,en-IN"
    }

    try:
        response = requests.post(
            GNANI_STT_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=60
        )

        response.raise_for_status()

        result = response.json()

        if not result.get("success"):
            raise ValueError(
                result.get("error", {}).get(
                    "message",
                    "Transcription failed"
                )
            )

        return result["transcript"]

    except requests.HTTPError as error:
        response = error.response
        raise RuntimeError(
            f"Gnani API returned {response.status_code}: {response.text}"
        )

    except requests.RequestException as error:
        raise RuntimeError(f"Gnani API request failed: {error}")