# Implementation status

Updated 2026-10-12. The [handoff](TOUCH_GRASS_CODEX_HANDOFF.md) remains the product specification.

## Implemented in source

- Project-local skill at `skills/wildmon/SKILL.md`.
- pnpm/Next.js App Router frontend with Tailwind, Geist font and design reference, Radix Dialog/Tabs, Prettier config, mobile camera fallback, responsive landing, dashboard, auth, collection, timed hunts, friends, challenges, ecosystems, settings, public profile, and leaderboard.
- FastAPI API with Pydantic validation, cookie/CSRF auth, PyMongo async access, private local/S3 image storage, idempotent discovery creation, server XP ledger, typed challenge requirements, deterministic one-to-one matching, timed ecosystem attempts, badges, and leaderboards.
- Five timed solo ecosystems: one active timer and one attempt per ecosystem, 1–168 whole-hour duration, dedicated captures, collection tags, deadline or manual finish, five-minute pending inference grace, fixed results, and one milestone award of 0/50/150/300 XP. Earlier untimed pack progress remains read-only history.
- Capture screens now lead with a camera action in quick discovery, hunts, friend challenges, and ecosystems. Existing-photo upload remains a small underlined discouraged fallback. The landing page and app shell use the motto `Touch grass.`
- LangChain/Gemma vision adapter with structured output checks and separate visual-trait question. MongoDB leased worker handles inference, retry, challenge deadlines, and results.
- AI Studio Gemma 4 transport through Google's native image `generateContent` endpoint; OpenAI-compatible hosts remain supported.
- An optional `BACKBOARD_KEY` sends the same image and prompt to Backboard's `google/<GEMMA_MODEL>` vision route after a failed Google request. The worker lease covers both providers for identification and trait validation.
- Seed/index script and 30-image evaluation harness. Seed species start unsupported until evaluation.
- Generated botanical hero photo optimized to a 376 KB JPEG.
- Same-origin Next.js API proxy and a reviewable Render Blueprint for web, API, and worker services.
- Browser-safe capture and challenge IDs using Web Crypto random bytes on LAN HTTP.
- Secret-safe Atlas/Gemma connectivity probe for running from a normal terminal.
- Focused AI Studio credential diagnostic separates key, model, text, and image failures without printing the key.
- VS Code workspace settings select the API uv virtual environment and add the API source root to Pylance import resolution.
- Timed-hunt focus XP is reconciled by the worker, including a short grace period for visibility signals after the deadline; the hunt summary displays focus bonus XP separately.
- Discovery cards open a dedicated detail page, and the hunts page lists recent sessions with direct summary links. Hunt summaries now include private image URLs. Browser uploads target 2 MB; the worker separately bounds larger images sent to Gemma while retaining the stored original.
- Failed identifications can be retried from capture and discovery detail using the existing discovery/job, with a compare-and-set job transition. "Needs review" is shown as "Uncertain identification," with tentative names labelled "Possible." A unique discovery-source XP key protects against overlapping worker awards.
- Isolated walkthrough tooling in `tools/video`: real Chrome captures, deterministic HTML/SVG animation, scene narration, captions, FFmpeg export, and reproduction instructions. It adds no dependencies to the production frontend.

## Verified here

- pnpm and uv dependencies installed; `pnpm-lock.yaml` and `apps/api/uv.lock` exist. uv's existing cache was copied to `/private/tmp` for an offline sync.
- Ruff lint and format checks pass. Thirty-eight API tests pass, including timed ecosystem scoring, duration bounds, evidence isolation, attempt admission rules, pending-photo settlement and once-only milestone XP, native Gemma transport, Backboard fallback image transport, nullable primary-subject review handling, async XP cursor, focus reward reconciliation, large-image/orientation preparation, retry idempotency, concurrent discovery XP protection, and the deployed XP index specification.
- Prettier check, frontend TypeScript check, OpenAPI schema export/type generation, and Next.js production build with webpack pass for the timed ecosystem changes.
- Local `.env` loads with Atlas URI, `wildmon` database, Gemma key/model, and a non-default JWT secret. Secret values were not printed.
- Approved live checks reached the local frontend (HTTP 200), API health (`database: connected`), and AI Studio. A real Gemma image diagnostic returned a candidate in 36.2 seconds. This confirms transport, not species accuracy.
- Chrome authenticated with the owner's authorized account, read two verified discoveries (papaya and Golden Pothos, 10 XP each), previewed an existing photo, started/finished one short empty hunt, and captured collection, challenge builder, pack checklist, badges, and weekly/all-time leaderboard screens. No photo was resubmitted and no friend invitation was sent.
- Gemini `gemini-3.8-flash-tts` generated eight narration clips. The live voice catalog confirms Charon is male, en-US, US region, General American accent. Temporary login credentials and the dedicated browser profile were removed after capture.
- Walkthrough tooling passes Ruff lint/format, Node syntax, and Prettier checks. All eight chapter previews were visually inspected, along with frames from the final MP4 and its ending. The finished walkthrough is 116.61 seconds, 1920×1080, H.264 at 30 fps with 48 kHz AAC narration. A full FFmpeg decode passes; measured narration is -16.34 LUFS with no clipping. Audio composition uses exact PCM sample offsets, and export duration is checked against the timeline.
- Video deliverables are `artifacts/wildmon-walkthrough.mp4`, `artifacts/wildmon-walkthrough.srt`, `artifacts/wildmon-narration.md`, and `artifacts/wildmon-video-source.zip`. The source archive includes animation/render code, actual captures, font license, narration clips, voice provenance, and reproduction instructions; it excludes credentials and environment files.

## Remaining validation and limitations

- Earlier sandbox-only network probes failed before authentication; approved network execution subsequently succeeded. Restricted execution still requires network/browser permission.
- Earlier short model timeouts and Google HTTP 500 errors were diagnosed separately. The worker has a configurable 120-second model read timeout and a lease sized for two calls. The user now confirms image processing works, and the live collection contains verified results. The 30-image accuracy evaluation remains outstanding.
- Google's inline-image documentation gives a 20 MB total request limit; the existing 6 MB upload limit is below it. The new 2 MB compression path reduces payload size but has not been tested with a fresh iPhone HEIC/JPEG capture or tied to the earlier provider HTTP 500 responses.
- Manual retry and the unique XP index have unit coverage but have not yet been exercised with a live failed Gemma job. The worker and seed script now request the same `$exists: true` partial index already present in Atlas; the previous `$type: "string"` request conflicted with it and prevented worker startup.
- Backboard fallback has mocked transport coverage only. The sandbox could not connect to Backboard's live model catalog, so actual key validity, model availability, and image response still need a live worker run.
- A live Backboard response returned `primary_subject: null`; the vision schema now accepts this abstention and the worker records it as uncertain identification without awarding XP. The log now distinguishes a received fallback response from a validated identification.
- Focus measures paired app-hidden intervals, not device screen state; an unpaired hidden signal cannot earn focus XP. The new worker reconciliation path has unit tests but has not yet been observed in a live timed hunt.
- Lighthouse, automated mobile-browser regression checks, a full two-account challenge, and measured species activation have not run. The walkthrough uses existing processed discoveries; its challenge synchronization is explicitly labeled as an animated explanation.
- Render deployment needs a private S3-compatible bucket and its CORS policy. The Blueprint has not been synced or deployed.
- The timed ecosystem seed could not reach Atlas from this restricted environment: DNS SRV queries to 8.8.8.8 and 1.1.1.1 returned `Operation not permitted`. Run `cd apps/api && uv run python -m scripts.seed` in a terminal with network access to create the two new packs. Live timed capture and deadline behavior has not yet been exercised against Atlas.

## Remaining product work

- Confirm index/catalog seed state and continue live integration checks for flows beyond the authenticated walkthrough.
- Evaluate at least 30 labeled nature/negative photos, enable only measured species, and complete a real two-account mobile-browser demo.
- Declare response schemas for the remaining FastAPI routes and replace temporary frontend view models with generated OpenAPI types.
- The five seeded ecosystems use broad categories until model/category evaluation validates narrower targets. Garden Life currently accepts two distinct photos of flowering plants without requiring distinct species.
- Complete offline IndexedDB queue, public image sharing, photo/account deletion, deployment, and outdoor test evidence. Focus is a conservative app-visibility estimate; challenge focus tie-break is not used.
