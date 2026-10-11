"""Build sample-exact narration, preserving each complete normalized speech clip."""

import json
import subprocess
import tempfile
import wave
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent
RATE = 48000


def main() -> None:
    """Place speech at each chapter's start, then pad its remaining duration.

    Composition uses PCM samples rather than filter timestamps, which can shift
    across independently normalized clips. Refuse to truncate spoken audio.
    """
    timeline = json.loads((DIRECTORY / "timeline.json").read_text())
    with (
        tempfile.TemporaryDirectory(prefix="wildmon-audio-") as temporary,
        wave.open(str(DIRECTORY / "audio/narration.wav"), "wb") as output,
    ):
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(RATE)
        previous_end = 0
        for scene in timeline["scenes"]:
            normalized = Path(temporary) / f"{scene['id']}.wav"
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-i",
                    str(DIRECTORY / "audio" / f"{scene['id']}.wav"),
                    "-af",
                    f"atempo={timeline['tempo']},loudnorm=I=-16:TP=-1.5:LRA=7",
                    "-ar",
                    str(RATE),
                    "-ac",
                    "1",
                    "-c:a",
                    "pcm_s16le",
                    str(normalized),
                ],
                check=True,
            )
            with wave.open(str(normalized), "rb") as source:
                speech = source.readframes(source.getnframes())
            end = round(scene["end"] * RATE)
            target = end - previous_end
            previous_end = end
            lead = round(0.3 * RATE)
            tail = target - lead - len(speech) // 2
            if tail < 0:
                raise RuntimeError(
                    f"Narration exceeds chapter {scene['id']}; extend its duration"
                )
            output.writeframes(b"\0\0" * lead + speech + b"\0\0" * tail)
    print(f"Sample-exact narration: {timeline['duration']:.3f}s, 48 kHz", flush=True)


if __name__ == "__main__":
    main()
