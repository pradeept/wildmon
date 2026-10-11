# Wildmon

Wildmon is a mobile-first nature discovery game. Photograph one living thing, let a vision-capable open-weight Gemma model inspect it, and build a collection from verified results. Timed hunts, friend challenges, ecosystem checklists, badges, and XP make exploring together playful without keeping the phone in hand.

This is an implementation in progress. See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for what has actually been tested.

## Architecture

```mermaid
flowchart LR
  Browser --> Web[Next.js mobile website]
  Web --> API[FastAPI game API]
  API --> Mongo[(MongoDB Atlas)]
  API --> Storage[(Private S3-compatible storage)]
  Worker[Python worker] --> Mongo
  Worker --> Storage
  Worker --> Gemma[Gemma vision endpoint]
```

FastAPI owns authentication, eligibility, matching, XP, challenge timing, pack progress, and leaderboards. Next.js handles the web experience and proxies `/api/v1` to FastAPI so browser cookies stay on one origin. The worker claims durable MongoDB jobs for inference and closes challenges even when browsers are closed. LangChain composes prompt construction and model transport. AI Studio Gemma uses Google's native `generateContent` API; other OpenAI-compatible model hosts use the alternate adapter. Results are validated with Pydantic and resolved against a curated catalog before any exact-species award.

The interface follows the [Geist design system reference](https://vercel.com/geist/introduction) for clear typography, high-contrast surfaces, and disciplined spacing. It uses the Geist font, Tailwind CSS, and Radix primitives with a Wildmon forest and butterfly palette. The official Geist documentation is a design reference here, not an installed Vercel component package.

## Local setup

Requirements: pnpm, uv, Python 3.12+, MongoDB Atlas or local MongoDB, and an endpoint serving a **vision-capable Gemma** model. Google documents [Gemma 4 on the Gemini API](https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api); choose a model your account actually serves and evaluate it before enabling exact species.

Run each setup block from the repository root.

1. Install frontend packages:

   ```bash
   pnpm install
   cp apps/web/.env.example apps/web/.env.local
   ```

2. Install backend packages and configure secrets:

   ```bash
   (cd apps/api && uv sync && { test -f .env || cp .env.example .env; })
   ```

   Edit `apps/api/.env` with `MONGODB_URI`, a random `JWT_SECRET`, `GEMMA_BASE_URL`, `GEMMA_API_KEY`, and `GEMMA_MODEL`. Do not commit secrets. Use `STORAGE_MODE=local` for development. For production use a private S3-compatible bucket and fill the `S3_*` settings. `apps/web/.env.local` only needs `API_PROXY_TARGET` when the API is not at `http://localhost:8000`.

   VS Code settings point Pylance at `apps/api/.venv` when the repository root is open, and at `.venv` when `apps/api` is open directly. If VS Code previously cached another interpreter, run **Python: Select Interpreter** and choose `apps/api/.venv/bin/python` (or `.venv/bin/python` from the API folder), then reload the window.

3. Seed indexes and provisional catalog:

   ```bash
   (cd apps/api && uv run python -m scripts.probe_services)
   (cd apps/api && uv run python -m scripts.seed)
   ```

   The probe checks Atlas and a real Gemma image call without printing keys. Its bundled image is synthetic and does not count toward model evaluation.

   If the AI Studio connection fails, run the focused credential check from your own terminal:

   ```bash
   cd apps/api && uv run python -m scripts.check_gemma_credentials --vision
   ```

   It checks key access, the configured model, text generation, and an image request in that order. It prints Google's bounded error message with the key redacted and distinguishes connection, upload, and response timeouts. Generation waits up to 120 seconds by default; use `--timeout 180` for a longer check. Omit `--vision` to skip the image request.

   For a fast image-only comparison on another supported Gemma model, run `uv run python -m scripts.check_gemma_credentials --vision-only --model gemma-4-26b-a4b-it` from `apps/api`. This override tests the model without changing `.env`.

   After switching `GEMMA_MODEL` to a model that passes the image check and restarting the worker, restore submissions that exhausted retries on Google HTTP 500 with `uv run python -m scripts.requeue_gemma_500 --apply` from `apps/api`. Run without `--apply` first to see the eligible count.

   The worker's model read timeout defaults to 120 seconds via `GEMMA_TIMEOUT_SECONDS`; increase it in `apps/api/.env` only if real image calls need longer. Restart the worker after changing this setting.

4. Run these in separate terminals:

   ```bash
   cd apps/api && uv run uvicorn app.main:app --reload --port 8000
   cd apps/api && uv run python -m app.worker
   pnpm dev:web
   ```

Open the website at `http://localhost:3000`; API health is at `http://localhost:8000/api/v1/health`, API docs at `http://localhost:8000/docs`. Browser requests use the website's `/api/v1` proxy, including private image URLs and local-development uploads.

Timed free hunts can award +25, +60, or +100 estimated in-app focus XP after at least one verified discovery. The browser records app-hidden and visible-again events, and the server counts only paired intervals after capture/finish allowances. It cannot prove the phone screen was physically off. The worker completes hunts and reconciles focus XP even when the summary is closed; a visible-again event may arrive up to two minutes after the deadline. Keep the worker running. Quick captures have no focus bonus.

For testing from another device on your LAN, open `http://<computer-ip>:3000` and set `WEB_ORIGIN=http://<computer-ip>:3000` in `apps/api/.env`. Next.js still proxies API requests to `http://127.0.0.1:8000` on the computer, so the phone never needs to reach its own `localhost`. If the computer's LAN IP changes, update `allowedDevOrigins` in `apps/web/next.config.ts` and restart both development servers after changing these settings.

To generate frontend OpenAPI types after dependency installation:

```bash
cd apps/api && uv run python -m scripts.export_openapi
cd ../web && pnpm typegen
```

The generated types are checked in at `apps/web/src/lib/api-types.ts`. Some frontend view models remain hand-maintained because their FastAPI response schemas still need to be declared.

## Render deployment

`render.yaml` is a reviewable Blueprint, not a deployed service. It defines free Next.js and FastAPI web services and a **paid, continuously running worker**. Set `API_PROXY_TARGET` to the deployed API URL and `WEB_ORIGIN` to the deployed website URL. The Blueprint prompts for Atlas, S3, and Gemma secrets. Add both Render services' outbound IP ranges to Atlas Network Access. The API seeds indexes and the provisional catalog at startup.

Render Free web services sleep after 15 minutes without traffic and lose local files on restart, so use `STORAGE_MODE=s3` with a private bucket. The worker cannot read files from the API service's disk. Configure the bucket's browser CORS policy to permit `PUT` from the website origin with the `Content-Type` header. The free web services can cold-start slowly; the paid worker continues processing and enforcing challenge deadlines. Render's [Free service limits](https://render.com/docs/free), [background worker docs](https://render.com/docs/background-workers), and [Atlas guide](https://render.com/docs/connect-to-mongodb-atlas) describe these constraints.

## Model evaluation

Species in the seed catalog start with `supported: false`. The app can show category-level results, but exact-species challenge targets remain unavailable until supported species are deliberately enabled after evaluation.

Prepare at least 30 labeled photos including plants, birds, insects, blurry or multi-subject images, and unrelated images. Use `apps/api/evaluation/manifest.example.jsonl` as the JSONL format. Then run:

```bash
cd apps/api
uv run python -m scripts.evaluate_model evaluation/manifest.jsonl --output model-evaluation.json
```

The report includes exact-species accuracy, category precision, false positives on negative images, abstention, and median/p95 latency. Review the per-photo output before changing any species document to `supported: true`. Model confidence text is not treated as calibrated probability. Rarity is not scored without cited regional data.

## Test and demo path

```bash
cd apps/api && uv run pytest
pnpm --filter web lint
pnpm --filter web build
```

Register two accounts, send and accept a friend request, take a quick capture, start and finish a timed hunt, create a category/trait challenge, join an ecosystem pack, and view both leaderboard scopes. Exact-species challenge targets require the evaluation gate above. Keep the worker running for inference and challenge deadlines.

Wildlife guidance: photograph without touching, feeding, picking, approaching nests, or entering unsafe or private locations. Images are private to the owner in the current API. Public sharing and account deletion are still outstanding.
