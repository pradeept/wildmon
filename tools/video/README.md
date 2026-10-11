# Wildmon walkthrough

A reproducible 1920 × 1080 film: real Chrome captures, deterministic HTML/SVG animation,
Gemini narration, burned captions, and a separate SRT file. Production app code is untouched.

## Deliverables

- `../../artifacts/wildmon-walkthrough.mp4` — H.264 / AAC, 30 fps, fast-start MP4.
- `../../artifacts/wildmon-walkthrough.srt` — separate captions.
- `../../artifacts/wildmon-narration.md` — editable narration.
- `film.html`, `scenes.json`, `timeline.json` — editable visual source and timing.
- `assets/` — genuine app captures; `audio/` — narration clips and voice provenance.

Generated photos, captures, audio, and video are ignored by Git. They contain the owner's
authorized account content. Login credentials are read from a private temporary file and
are never written to this directory or into the film.

The original generated landing-page hero is used as a decorative brand asset. Discovery
photographs and UI states come from the live account. Narration is AI-generated; the vector
leaves, butterfly, and explanatory diagrams are drawn in the source. Geist's license is
included alongside the font assets.

## Requirements

Node 22+ (built-in WebSocket), pnpm, Google Chrome, FFmpeg/ffprobe, and Python 3.
Regenerating narration also needs the original project's API uv environment.
No video dependencies are added to the frontend. On macOS Chrome is discovered at the normal
application path; set `CHROME_PATH` to override it.

## Capture

Run the existing web/API/worker services. Create a private temporary JSON file containing
`email` and `password`, chmod 600, outside the repository. Then run:

```sh
WILDMON_VIDEO_LOGIN_FILE=/private/tmp/wildmon-video-login.json pnpm --dir tools/video capture
```

Set `WILDMON_ORIGIN` to override `http://localhost:3000`. Capture uses a separate headless Chrome
profile and removes that profile on exit. It logs in, reads the real collection, previews an
existing photo without submitting it, starts and finishes one short empty hunt, and reads
the remaining feature screens. It sends no friend invitation and changes no leaderboard
privacy setting. Remove your temporary credential file after capture.

## Narrate

```sh
apps/api/.venv/bin/python tools/video/narrate.py --probe
apps/api/.venv/bin/python tools/video/narrate.py
```

The script loads the existing AI Studio key privately from `apps/api/.env`. It chooses an
available speech model and uses catalog-verified male en-US Charon. Existing clips are reused;
remove a scene's generated WAV after editing its text to regenerate that clip. For an explicit
offline fallback, run `narrate.py --local` (installed male US Reed voice).

Speech generation follows Google's [speech guide](https://ai.google.dev/gemini-api/docs/speech-generation)
and [voice catalog API](https://ai.google.dev/api/voices). WAV and legacy raw PCM are handled
separately. Model, voice, region, accent and provider are recorded in `audio/voice.json`.

## Preview and render

```sh
pnpm --dir tools/video preview
pnpm --dir tools/video render
```

Preview exports one PNG per chapter. Render measures every audio clip, constructs the timeline
and SRT, normalizes speech, composes it at exact PCM sample offsets, and sends deterministic
Chrome frames directly to FFmpeg. A silent video master is rendered before the audio is muxed,
and the exported duration is checked against the timeline. A tempo adjustment is applied only
if necessary to stay close to two minutes; audio is never cut.

`window.renderAt(seconds)` in `film.html` is the animation API. Screenshots are genuine;
cursor motion, leaves, butterfly, challenge mechanics and architecture are original SVG/HTML.
The preview-to-collection cut is explicitly labeled as earlier verified discoveries.
The short hunt honestly shows an empty summary. Challenge mechanics are labeled as an animated
explanation because the account has no existing challenge. Pack and badge progress are shown
as recorded. Deployment and unevaluated species accuracy are not claimed.

Captions are phrase-level, timed proportionally within each speech clip; they are not
word-level forced alignment. The final timing and actual duration are in `timeline.json`.

## Check the output

```sh
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate -show_entries format=duration -of json artifacts/wildmon-walkthrough.mp4
ffmpeg -v error -i artifacts/wildmon-walkthrough.mp4 -f null -
```

Inspect the preview PNGs for layout, legibility, genuine states, and credential privacy.
