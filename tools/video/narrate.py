"""Generate scene narration with the existing AI Studio key, never logging credentials.

Use --probe to inspect only TTS capabilities. Normal execution reuses existing clips;
--local explicitly selects the installed male en-US Reed voice as a fallback.
"""

import argparse
import base64
import json
import re
import subprocess
import sys
import wave
from pathlib import Path

import httpx

DIRECTORY = Path(__file__).resolve().parent
ROOT = DIRECTORY.parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
from app.core.config import Settings


def save_audio(part: dict, output: Path) -> None:
    """Preserve provider WAV headers, or wrap legacy 16-bit mono PCM once."""
    raw = base64.b64decode(part["data"])
    if raw.startswith(b"RIFF"):
        output.write_bytes(raw)
        return
    mime = part.get("mimeType", part.get("mime_type", ""))
    if "l16" not in mime.lower() and "pcm" not in mime.lower():
        raise RuntimeError(f"Unexpected audio type: {mime}")
    match = re.search(r"rate=(\d+)", mime)
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(int(match.group(1)) if match else 24000)
        wav.writeframes(raw)


def main() -> None:
    """Select a supported TTS model; fail safely so fallback stays explicit."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--local", action="store_true")
    args = parser.parse_args()
    scenes = json.loads((DIRECTORY / "scenes.json").read_text())
    output = DIRECTORY / "audio"
    output.mkdir(exist_ok=True)
    info = {"provider": "macOS", "voice": "Reed", "language": "en-US"}
    if args.local:
        for scene in scenes:
            target = output / f"{scene['id']}.wav"
            aiff = output / f"{scene['id']}.aiff"
            subprocess.run(
                ["say", "-v", "Reed", "-r", "155", "-o", str(aiff), scene["text"]],
                check=True,
            )
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff), str(target)],
                check=True,
            )
    else:
        key = Settings(_env_file=ROOT / "apps/api/.env").gemma_api_key
        if not key:
            raise RuntimeError("No AI Studio key configured")
        with httpx.Client(
            base_url="https://generativelanguage.googleapis.com/v1beta/",
            headers={"x-goog-api-key": key},
            timeout=180,
        ) as client:
            response = client.get("models", params={"pageSize": 1000})
            if response.status_code != 200:
                raise RuntimeError(f"Model list returned HTTP {response.status_code}")
            models = [
                m["name"].removeprefix("models/")
                for m in response.json().get("models", [])
                if "tts" in m["name"]
            ]
            print("Available TTS models:", ", ".join(models), flush=True)
            voices = client.get(
                "voices",
                params={"gender": "male", "language_code": "en-US", "page_size": 100},
            )
            catalog = (
                voices.json().get("voices", []) if voices.status_code == 200 else []
            )
            chosen = next(
                (v for v in catalog if v.get("id", "").lower() == "charon"), None
            )
            print(
                "US male voice catalog:",
                voices.status_code,
                json.dumps(
                    chosen
                    or [
                        {
                            k: v.get(k)
                            for k in ("id", "gender", "accent", "language_code")
                        }
                        for v in catalog[:4]
                    ]
                ),
                flush=True,
            )
            if args.probe:
                return
            preferences = [
                "gemini-3.8-flash-tts",
                "gemini-3.1-flash-tts-preview",
                "gemini-2.5-flash-preview-tts",
                "gemini-2.5-pro-preview-tts",
            ]
            model = next((m for m in preferences if m in models), None)
            if not model:
                raise RuntimeError(
                    "No supported TTS model available; use --local fallback"
                )
            voice = (chosen or {}).get("id", "Charon")
            info = {
                "provider": "Google Gemini",
                "model": model,
                "voice": voice,
                "language": "en-US",
                "catalog": chosen,
            }
            for scene in scenes:
                target = output / f"{scene['id']}.wav"
                if target.exists():
                    print("Reuse", scene["id"], flush=True)
                    continue
                print("Generating", scene["id"], flush=True)
                if model.startswith("gemini-3.8"):
                    payload = {
                        "model": model,
                        "input": [
                            {
                                "type": "user_input",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": scene["text"],
                                        "annotations": [
                                            {
                                                "type": "speech_metadata",
                                                "style": "Warm, informative documentary narration. Conversational, brisk but clear, with short pauses between sentences.",
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                        "response_format": {"type": "audio"},
                        "generation_config": {"speech_config": [{"voice": voice}]},
                    }
                    result = client.post("interactions", json=payload)
                else:
                    payload = {
                        "contents": [
                            {
                                "parts": [
                                    {
                                        "text": "Read the following verbatim in a natural adult male American English voice. Warm, conversational documentary narration, moderately brisk (around 160 words per minute). Do not speak these instructions.\n\n"
                                        + scene["text"]
                                    }
                                ]
                            }
                        ],
                        "generationConfig": {
                            "responseModalities": ["AUDIO"],
                            "speechConfig": {
                                "voiceConfig": {
                                    "prebuiltVoiceConfig": {"voiceName": voice}
                                }
                            },
                        },
                    }
                    result = client.post(
                        f"models/{model}:generateContent", json=payload
                    )
                if result.status_code != 200:
                    error = result.json().get("error", {})
                    # Never print URL/header or raw provider response, which may contain credentials.
                    raise RuntimeError(
                        f"TTS HTTP {result.status_code}: {error.get('status', 'unknown')}"
                    )
                data = result.json()
                if model.startswith("gemini-3.8"):
                    parts = [
                        c
                        for step in data.get("steps", [])
                        for c in step.get("content", [])
                        if c.get("type") == "audio"
                    ]
                    part = parts[-1] if parts else None
                else:
                    parts = [
                        p["inlineData"]
                        for c in data.get("candidates", [])
                        for p in c.get("content", {}).get("parts", [])
                        if "inlineData" in p
                    ]
                    part = parts[0] if parts else None
                if not part:
                    raise RuntimeError("TTS returned no audio")
                save_audio(part, target)
                print("Saved", scene["id"], flush=True)
    (output / "voice.json").write_text(json.dumps(info, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (httpx.HTTPError, RuntimeError) as exc:
        # HTTP exceptions may embed URLs; report only their class for transport errors.
        print(
            str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__,
            file=sys.stderr,
        )
        sys.exit(1)
