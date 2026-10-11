# Touch Grass — Codex Implementation Handoff

**Version:** 1.3 (timed ecosystem challenges)
**Date:** 2026-10-12
**Platform:** Next.js website, Python/FastAPI backend API, model inference adapter. **No native app.**  
**Goal:** A playable outdoor nature-catching website using open-weight AI, with quick discoveries, timed hunts, friend challenges, ecosystem packs, badges, and friend/global leaderboards.
**Motto:** Touch grass.

## 0. Instructions to Codex

Treat this file as the product source of truth. Implement working vertical slices rather than scaffolding every module at once. Inspect the repository before making changes. If it is empty, initialize the layout in §3. Do not claim an unavailable capability works. Maintain `IMPLEMENTATION_STATUS.md` with completed items, blockers, setup instructions, tests run, and actual model/deployment decisions. Do not introduce native apps or new infrastructure for speculative scale. All scoring and authorization belong on the server. Use real open-weight inference in the demo, with explicit error/uncertain states; mock inference is permitted **only in tests and explicitly labeled local demo fixtures**.

## 1. Locked decisions

1. **Free Hunt:** (a) quick single-photo capture without starting a timer; (b) optional explicit timed sessions with Start/Finish. Both earn discovery XP; only timed sessions qualify for focus bonuses.
2. **Friend challenges:** creator may use **specific supported species** (e.g. Neem) **or broader supported categories/traits** (e.g. any butterfly, distinct leaf shapes). Challenge requirements are typed and may be mixed in one challenge. The UI must show the required evidence and identification specificity.
3. **Challenge start:** both players accept and mark **Ready**. The server atomically sets a common `startedAt` and `deadlineAt` once both are ready. No participant can start alone.
4. **Ecosystem challenges:** a user can start one timed ecosystem at a time, for 1–168 whole hours, and gets one attempt per ecosystem. Only new photos submitted through that attempt count. One photo fills at most one checklist unit. Existing untimed pack progress remains read-only history.
5. **Backend:** Python **FastAPI** is the single source of truth for authentication, discoveries, game rules, XP, challenges, ecosystem packs, leaderboards, and AI orchestration. Next.js is the website/UI, not an alternate game backend.
6. **AI:** evaluate a vision-capable **Gemma** model first. Choose the production model based on measured accuracy, latency, cost, and hardware feasibility, not partner points. Keep the inference adapter replaceable.
7. **Leaderboards:** global and accepted-friends leaderboards, weekly and all-time. Use **eligible, server-awarded XP**, not total photograph count.
8. **Original concept retained:** short capture interactions, phone back in pocket, post-session identification/reveal, rarity when supported, badges and shareable summaries.

## 2. Product scope and terms

**Discovery:** A photograph with provenance, user, timestamps and an AI review record. It might be unverified.  
**Verified observation:** A discovery with a valid, supported identification at the required taxonomic/category granularity.  
**Species collection:** Distinct verified species seen by user; category-only observations do not count as identified species.  
**Quick capture:** One-off discovery, no active hunt or focus bonus.  
**Timed hunt:** Session starts on server, can contain many discoveries, ends explicitly or on timeout.  
**Friend challenge:** One creator, one opponent, fixed shared requirements and deadline.  
**Ecosystem challenge:** Timed solo checklist with an explicit start, dedicated photo submission, and a fixed result.

**Non-goals:** native apps, chat, endless feed, trading/monetization, complex live GPS tracking, device-wide screen-time tracking, claims of scientific conservation rarity, guaranteed anticheat, and full biodiversity taxonomy coverage.

## 3. Recommended implementation stack

- Repository layout: `apps/web` Next.js App Router + TypeScript + Tailwind; `apps/api` **Python 3.12+ / FastAPI** (the sole backend API); `apps/api/app/{api,core,models,schemas,services,repositories,workers,ai}`; `apps/api/tests`; `scripts` for seeds and indexes. Keep the AI adapter inside the FastAPI codebase. A separate model-serving process is allowed only when required by GPU hosting, not as a second business backend.
- Python tooling: `uv` (or pip with a locked dependency file), **Pydantic v2** request/response models and settings, FastAPI dependency injection, `pymongo` AsyncMongoClient for async MongoDB access, `httpx` for hosted AI inference, `pytest` + `pytest-asyncio` for tests. Frontend consumes the FastAPI-generated **OpenAPI schema**; optionally generate a typed TypeScript client using `openapi-typescript`. No duplicate hand-maintained TypeScript domain model where schema generation works.
- Architecture: thin FastAPI routers -> application/domain services -> MongoDB repositories; AI inference port/adapter; domain-level pure Python functions for scoring, one-to-one objective matching, and challenge winner rules. Use explicit MongoDB unique indexes and compare-and-set transitions.
- DB: **MongoDB Atlas**; explicit indexes and idempotent writes. MongoDB Atlas is an optional Hacktoberfest partner category.
- Storage: private S3-compatible bucket and signed uploads, with safe public thumbnails. Never store binary image data inside MongoDB.
- API runtime: `uvicorn app.main:app` (or production ASGI equivalent). Organize routers with `/api/v1`, startup/shutdown using lifespan, shared DB client managed through app state/dependencies, and centralized exception handling. Do not implement business routes using Next.js API handlers.
- AI: implement `VisionIdentifier` adapter. Try **Gemma** multimodal first (image-capable version, not text-only small checkpoint); run a small evaluation set before locking. Model runner may be hosted separately or local. Configurable base URL, credentials, model ID, timeouts, retries, and prompt version.
- Deployment: Next.js on a suitable frontend provider, FastAPI ASGI service on **Render** if practical, DB on Atlas, model on available GPU/inference provider. Render is optional partner category. Do not rely on a sleeping process for challenge expiry; deploy a scheduled job or durable recurring finalizer.
- Background execution: **do not use FastAPI `BackgroundTasks` for durable inference, deadline enforcement, or score finalization**. Start with a MongoDB-backed `processing_jobs` collection with leases, retry/backoff, and a separately running Python worker/periodic scheduler. Challenge expiry must run even when no user browser is open. If actual throughput or reliability requires it, switch to **Celery + Redis** as a deliberate later step (you used this successfully in Noteesta); Celery is not mandatory for the MVP.
- Avoid WebSockets, Redis, and service proliferation until they solve an observed need; polling is enough for progress and results.
- Test stack: **pytest / pytest-asyncio** for Python domain logic, FastAPI integration tests using `httpx.AsyncClient` + ASGI transport, and model parsing/validation; Playwright for critical mobile-browser flows. Optional Vitest for isolated frontend code only.

## 4. Primary UX and navigation

Public: `/`, `/login`, `/register`, `/leaderboard`, `/u/[username]` (public profile only).  
Authenticated: `/dashboard`, `/capture`, `/hunts`, `/hunts/[id]`, `/hunts/[id]/summary`, `/collection`, `/friends`, `/challenges`, `/challenges/new`, `/challenges/[id]`, `/challenges/[id]/results`, `/ecosystems`, `/ecosystems/[slug]`, `/badges`, `/settings`.

Desktop sidebar: Explore, Ecosystems, Collection, Challenges, Friends, followed by a Rewards group containing Leaderboard and Badges. On mobile, bottom nav: Explore, Ecosystems, Collection, Challenges, Profile. Keep capture button prominent. Capturing an image must require minimum taps. Use HTTPS and `getUserMedia` where available; fall back to `<input type=file accept=image/* capture=environment>` and explain permission failures. Do not promise camera works offline in every browser. Use IndexedDB offline queue when available, and upload status indicators. Limit compressed image size; keep the original image securely if required for verification.

### A. Quick discovery

Dashboard -> `Quick Capture` -> photo -> preview/retry -> submit -> `Queued/Identifying/Verified/Needs review/Unidentified` -> result card + collection/XP if verified. No hunt timer, no focus bonus. Show pending state rather than block camera UI waiting for inference. Capture one primary organism per photo for MVP; multiple subjects produce `needs_review` or request crop/retake.

### B. Timed Free Hunt

Choose a duration (default 20 minutes, presets 10/20/30), press Start -> server stores `startedAt`, `deadlineAt` -> minimal capture-only interface -> intermittent photos -> tap Finish or auto-end at deadline -> processing -> end-of-hunt reveal, points, valid/invalid/uncertain photos, collection changes, and optional share card. A photo must be submitted/queued with session association during active session. Server timestamps and captures are best-effort evidence only. Pictures submitted after a deadline are eligible only if accepted under the capped sync-grace rules below.

### C. Friend challenge

Creator chooses accepted friend, sets 3–5 requirements (typed as `species`, `taxon_category`, or `visual_trait`), selects 15/20/30 minute duration, submits invite. Opponent accepts; each taps Ready; when both Ready server changes state to `active` atomically, sets common start/deadline and issues each participant a hunt. Users photograph targets and put phone away. UI may show target list but should not require model processing while hunting. `Done` immediately locks that player’s captures, even when opponent continues; challenge becomes `verifying` only after both lock or shared deadline. Allow server-scheduled deadline auto-finalization. Server independently validates evidence; result then publishes winner/draw, badge, XP, share link.

### D. Ecosystem pack

Browse five seeded ecosystems. The user chooses 1–168 whole hours and starts one attempt. The server starts the timer and accepts new photos through that ecosystem's upload entry while active. Those photos appear in Collection with an ecosystem tag and earn ordinary discovery XP. Earlier discoveries and other capture modes never fill this checklist. Finish or the deadline closes admission; accepted pending identification gets at most five minutes to settle. The result is Completed, Partially completed, or Couldn't complete. Each user gets one attempt per ecosystem, including a fresh attempt if they used the earlier untimed pack system. Older pack progress and XP remain read-only history.

## 5. Challenge requirement and scoring specification

Requirements must be immutable after invitation acceptance. Use a discriminated union:

```python
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field

class SpeciesRequirement(BaseModel):
    id: str
    kind: Literal["species"]
    species_id: str
    count: Literal[1] = 1

class CategoryRequirement(BaseModel):
    id: str
    kind: Literal["taxon_category"]
    category: Literal["plant", "bird", "insect", "butterfly", "flowering_plant", "tree"]
    distinct_species: int = Field(ge=0, default=0)
    count: int = Field(ge=1, default=1)

class TraitRequirement(BaseModel):
    id: str
    kind: Literal["visual_trait"]
    trait_code: str
    count: int = Field(ge=1, default=1)
    distinct_observations: bool = True

Requirement = Annotated[
    Union[SpeciesRequirement, CategoryRequirement, TraitRequirement],
    Field(discriminator="kind"),
]
```

Use snake_case in Python and documented camelCase JSON aliases if needed by the frontend; choose one wire convention and generate the client from OpenAPI.

`species`: must be identified to that exact catalog species.  
`taxon_category`: must be reliably validated as that category; when `distinctSpecies` is required, genus-only/category-only inference **does not** satisfy uniqueness. `count` sets observations required; for MVP use `distinctSpecies: 0` for simple category counts or require known species explicitly.  
`visual_trait`: use curated objective codes such as `serrated_leaf` or `yellow_flower`, and a dedicated model question/validator. Never turn a free-form user string into an unconstrained judge.

**Matching:** Use deterministic bipartite one-to-one assignment of verified discoveries to target slots to maximize satisfied requirements; no single observation satisfies two targets in the same challenge. Exclude duplicates and any captures outside permitted time. Do not rely on capture order. All matches must pass appropriate category/species/trait validation.

**Win rules (locked default):**
1. Compare weighted targets satisfied: exact species 3 pts, category 2 pts, visual trait 1 pt. A multi-count requirement grants its weight **per fulfilled unit**, not merely for complete rows. Both contestants share the same objective weights.
2. If equal, compare **number of target units** completed, to avoid accidental weight ties.
3. If equal, compare estimated focus bonuses only when data is sufficient and valid for **both** players; otherwise skip this tie-break.
4. If equal, compare earlier **server-received** Done timestamps, but only when both voluntarily finished before deadline.
5. Otherwise, draw. A player with zero matches cannot win solely from focus/time.

This scoring supports mixed exact/category requirements transparently. The user-facing challenge shows each requirement's points before accepting.

**Completion and race rules:** explicit `Done` is final for that player. Both Ready transitions and finalization are compare-and-set/idempotent. A deterministic scheduled job finalizes expired challenges, even if both browsers are closed. `verifying` waits for eligible inference jobs up to a short bounded processing timeout (e.g. 5 minutes); after timeout unresolved observations are excluded as unverified and can be displayed as pending review, with no silent fabricated identification. Publish results exactly once. Server evaluates locked evidence snapshots; never recalculate the competitive result unpredictably from later edits. Admin/manual review may trigger an explicit auditable correction flow after MVP.

**Sync grace:** client attempts upload immediately when online; server permits a small **post-end transfer window** (default 2 minutes) only for previously registered capture records made during the active session. Because browser capture timestamps are forgeable, do not claim tamper resistance. If no capture record was registered before expiry, post-expiry upload is not accepted for competitive score. Offline recordings may remain in a personal collection without influencing expired competition.

## 6. AI identification and verification

1. Store image privately and create pending discovery with idempotency token.
2. Check format, dimensions, safe size, obvious duplicate hash/perceptual similarity within a user's hunt; optionally image hygiene/non-nature rejection.
3. Ask configurable open-weight image model for: primary organism type; candidate taxon (`species/genus/family/category`); common/scientific name where supported; observable attributes; uncertainty; and whether picture is insufficient.
4. Validate structured output with typed schema. Resolve scientific names to **curated taxon catalog**; do not assume plausible scientific strings are correct. For known challenge targets use constrained candidate taxonomy where sensible; still allow `unknown` and avoid forcing match.
5. A taxonomy match is not scientific proof: mark `verified` only under conservative app-defined criteria. Otherwise `needs_review` or `unidentified`, with retake guidance. Confidence provided by generative models must not be assumed calibrated.
6. Independently test visual traits against explicit criteria. Reject unrelated/web screenshots when identifiable; cannot guarantee real-world authenticity.
7. Server awards points and updates pack/challenge eligibility exactly once after verification.

**Gemma-first evaluation:** choose a vision-capable Gemma 3 (4B+ or Gemma 3n variant) or newer eligible multimodal Gemma model based on available hosting and licensing. Test at least ~30 labeled nature photos spanning exact plants, birds, insects, categories, blurry/multiple objects, and irrelevant images. Track exact-species accuracy, category precision, false positive rate, correct abstention, and median/p95 latency. If exact-species quality is weak, keep Gemma for category/visual-trait checks and add a specialized open-weight nature classifier for species; document model contributions. Never advertise support for species that fail evaluation. Use demo data to seed 10–20 supported local species (not the entire world taxonomy).

**Rarity:** do not let an LLM declare conservation rarity. Phase 1 only shows `common/uncommon/rarely observed` for species with a cited, region-specific, curated source; otherwise show `not rated` and **zero rarity bonus**. Do not infer rarity from low AI confidence.

## 7. XP ledger, progress, achievements

All scoring is computed server-side. Append unique records to `xp_transactions` with unique `idempotencyKey`. Use transactions/atomic operations around reward issuance and derived totals. Daily caps prevent spam. Initial tunable rules:

| Award | XP | Conditions |
|---|---:|---|
| New unique verified species | +100 | Once per user/species lifetime |
| Repeat verified observation | +10 | At most twice per species/day; no same-session duplicate individual |
| Timed focus bonus | +25 / +60 / +100 | Valid estimated focus tier; capped once per hunt and max 3 hunts/day |
| Friend challenge participation | +40 | At least one valid target, only once |
| Friend challenge win | +200 | One winner only; draw gets no win XP |
| Perfect friend challenge | +100 | Every required target unit matched |
| Ecosystem milestone | +50 / +150 / +300 | At least one but less than half / at least half but incomplete / all checklist units; one reward per finalized attempt |

Optional rarity XP +30/+70 only after reliable rarity metadata is introduced; disabled in initial configuration.

**Focus tracking — web limitation:** listen to `visibilitychange`, `pagehide`, and limited active-page heartbeats; track app-visible intervals only, exempt up to 60 seconds for each valid camera capture and up to 60 seconds for Finish. Missing/unknown intervals must **not** be counted as verified screen-off time. Explicitly label metric `Estimated in-app focus`, not actual device-wide screen-off time. For MVP, award optional focus XP only to timed hunts with sufficient instrumentation and prevent focus from dominating friend-challenge outcomes. A user is never penalized for emergency phone use; no discovery XP deduction.

**Achievements:** First Discovery; Plant Collector (5 unique plants); Bird Spotter (3 unique birds); Bug Hunter (5 unique insects); First Victory; Five Wins; Perfect Hunt; Ecosystem Explorer; All Three Packs; Pocket Explorer (three sessions with top focus tier). Badge issuing must be idempotent.

**Leaderboards:** weekly UTC boundaries (document that this is UTC), all-time; scope `global` or `friends` (accepted mutual friends + self). Only public opt-in users listed globally. Sort XP desc, then verified unique species desc, then earlier achievement timestamp/user ID deterministically. Paginate. Users may opt out of global leaderboard; private profiles leak neither exact coordinates nor private images.

## 8. Initial ecosystem definitions

Represent slots as the same typed requirement matcher used in friend challenges. One verified photo fills at most one unit; species uniqueness is not required for current ecosystems.

- **Backyard Biodiversity:** one flowering plant, one butterfly, one insect, one bird, one tree.
- **Urban Wildlife:** one tree, one bird, one plant, one insect, one flowering plant.
- **Garden Life:** two flowering plants, one butterfly, one insect, one plant, one tree.
- **Pollinator Path:** two flowering plants, one butterfly, two insects.
- **Birdwatch Trail:** three birds, one tree, one flowering plant.

Persist an immutable slot snapshot, start/deadline/close/finalize timestamps, fulfilled units, evidence IDs, and idempotent milestone reward. Match only discoveries bound to this attempt. Keep the former `user_pack_progress` collection for read-only history.

## 9. Database collections and indexes

- `users` (`usernameLower` unique, `emailLower` unique, profile visibility, XP projection, settings).
- `friendships` (canonical sorted user pair unique, requester, status, timestamps).
- `species` (`scientificNameNormalized` + taxonomy source unique, category, supported, rarity provenance).
- `discoveries` (user, image object key, client/server timestamps, session association, AI result/status, duplicate hash, taxon/category/traits, idempotency token); unique (`userId`, `clientCaptureId`).
- `hunt_sessions` (user, mode, state, start/deadline/end, focus signals and computed bonus).
- `challenges` (inviter, invitee, requirements, invite/ready states, shared timing, result version, winner/draw, finalizedAt).
- `challenge_entries` (challenge/user/discovery unique, eligibility, locked flag, result match).
- `ecosystem_packs` (slug/version, slots, rewards).
- `ecosystem_attempts` (user/pack unique, one active attempt per user, deadline, slot snapshot, result and award state).
- `user_pack_progress` (read-only legacy pack history).
- `xp_transactions` (`idempotencyKey` unique, `userId`, `amount`, `type`, source, timestamp).
- `badges` (code unique), `user_badges` (user/badge unique or version-aware).
- `processing_jobs` (kind, record ID, lease owner/expiration, retry count, state, last error).

Use indexes for leaderboard period/scope, friend requests, discovery lookup, pending jobs, challenge due dates and user collections. Keep indexes targeted for a hackathon, not speculative.

## 10. API contracts (prefix `/api/v1`)

**Auth/profile:** `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /me`, `PATCH /me`, `GET /users/:username`.

**Friends:** `GET /friends`, `POST /friends/requests`, `POST /friends/requests/:id/accept`, `POST /friends/requests/:id/reject`.

**Discovery:** `POST /uploads/sign`, `POST /discoveries` (image key, clientCaptureId, optional sessionId/challengeId/ecosystemAttemptId), `GET /discoveries/:id`, `GET /discoveries`, `GET /collection`.

**Timed hunts:** `POST /hunts` (duration), `GET /hunts/:id`, `POST /hunts/:id/visibility`, `POST /hunts/:id/finish`, `GET /hunts/:id/summary`.

**Friend challenges:** `POST /challenges`, `GET /challenges`, `GET /challenges/:id`, `POST /challenges/:id/accept`, `POST /challenges/:id/decline`, `POST /challenges/:id/ready`, `POST /challenges/:id/done`, `POST /challenges/:id/captures` (register eligible capture), `GET /challenges/:id/results`. Participant evidence is linked through discovery creation and checked server-side.

**Ecosystems:** `GET /ecosystems`, `GET /ecosystems/:slug`, `POST /ecosystems/:slug/start`, `POST /ecosystems/:slug/finish`, `GET /ecosystems/:slug/results`.

**Other:** `GET /leaderboards?scope=friends|global&period=weekly|all-time`, `GET /badges`, `GET /me/badges`, `GET /health`.

Define Pydantic v2 request/response schemas, FastAPI dependency-based security, autogenerated OpenAPI, standardized error responses (`code`, `message`, optional details), authentication, authorization, and pagination. Return HTTP 409 for invalid challenge state transitions and 202 for pending AI jobs.

## 11. State machines and server invariants

**Discovery:** `uploaded -> queued -> processing -> verified | needs_review | unidentified | rejected | failed` (failed retryable; transitions auditable). Only final verified observations qualify for points/matching.

**Timed hunt:** `active -> finishing -> completed`; server-enforced timeout and expiry; preserve pending verification in results until terminal.

**Challenge:** `invited -> accepted -> ready_wait -> active -> verifying -> completed`; alternatives `declined`, `cancelled`, `expired` only from allowed states. Both ready before active; both done or deadline before verifying; one terminal final result; cannot edit targets after invitation accepted; only authorized participants see private evidence.

**Ecosystem:** `not_started -> active -> verifying -> completed | partial | missed`. Finish and deadline stop new submissions. Pending photos have a five-minute verification grace; result and bonus are fixed after finalization.

Protect multi-request races with atomic compare-and-set updates, unique keys, and idempotency tokens. Never trust client-submitted XP, validation status, unlocks, or winner.

## 12. Privacy, safety and integrity

- Follow no-harm wildlife practices: photograph only; do not touch, pick, approach nests, feed or disturb organisms. Warn against trespassing or unsafe locations.
- Remove/omit exact GPS and EXIF from publicly shared images. Do not expose threatened species locations. Location permission optional; handle no-location use gracefully.
- HTTPS, secure HTTP-only cookies, hashed passwords or hosted auth, rate limits, upload limits, CSRF protection if cookie auth, user content validation, private object keys, URL expiry.
- Duplicate-photo detection within a hunt; cap submissions and inference calls; record provenance but don't promise anti-cheat guarantees. Screenshots/replayed photos can fool browser-based systems.
- Expose model uncertainty and provide retake/review behavior. Do not award exact-species points for genus/category-only predictions.
- A user can delete their photos/account, subject to clearly documented implementation limitations.

## 13. Tests and acceptance scenarios

Implement automated tests for: first vs repeat XP; daily repeat cap; duplicate upload/idempotent scoring; same image reused in one session; exact-species vs category vs trait matching; one-to-one target assignment; both-ready atomic start; concurrent Ready; early Done and late opponent; deadline auto-close without browser; sync-grace limits; delayed/failed inference; win/draw tie-breaks; badge/reward exactly once; ecosystem upload isolation, expiry, partial/full milestones, and one attempt per pack; friends/global visibility; insufficient focus signals not treated as off-screen proof; expired job retry behavior.

**Minimum live end-to-end acceptance:**
1. Register two accounts and become friends.
2. Perform one quick capture and show a genuine Gemma (or measured replacement) inference with candidate/category/uncertainty.
3. Start a timed hunt, capture at least two organisms, finish, obtain summary and collection entries.
4. Create a mixed friend challenge (one exact supported species and one category), invite friend; both accept/ready; capture evidence; each presses Done; server produces consistent winner/draw and awards one-time bonuses/badge.
5. Start an ecosystem, submit new photos through its upload entry, finish or expire, and receive one milestone reward based on matched checklist units.
6. Verify both leaderboards reflect server-recorded XP.
7. Complete one outdoor mobile-browser test and record limitations.

## 14. Build phases and gates

**P0-A — Foundation and AI proof:** Next.js website + FastAPI app, Pydantic schemas/OpenAPI client, auth, async MongoDB, image storage, mobile camera fallback, Python model adapter, 30-image Gemma evaluation, supported taxonomy seed. **Gate:** real photo -> persisted candidate identification + uncertainty/error state.

**P0-B — Free Hunt:** quick capture, timed session, XP ledger, collection, focus estimate, summary. **Gate:** repeated requests don't duplicate rewards.

**P0-C — Friend Duel:** friends, typed objectives, accept/ready, timed evidence, Done, result worker, winner/tie rules, badges. **Gate:** two browsers complete one challenge end-to-end, even if AI jobs finish after both press Done.

**P0-D — Ecosystem challenges:** seed five choices, server-owned timers, dedicated uploads, deterministic matching, once-only milestone reward. **Gate:** expiry and result survive refresh/log out.

**P0-E — Competition:** global/friends leaderboards, sharing, mobile styling, privacy, deploy + actual outdoors demo.

**Post-hackathon:** broaden species catalog, calibrated rarity, moderation/manual review, robust offline sync, advanced anti-abuse, accessibility audit, richer badges, geographic fairness, friend groups, automated comparisons.

**Time constraint:** submission by **2026-10-11 23:59 PDT** (2026-10-12 12:29 IST). Deliver working proof before polishing; reduce scope rather than fake functionality. If unable to complete everything, prioritize A/B/C and one pack, then a minimal leaderboard; mark omitted features explicitly. Challenge submissions require a new project begun in the challenge window and explanation of open-source AI use.

## 15. Partner technology policy

Official Touch Grass eligible partner categories include **Gemma**, **Render**, **MongoDB Atlas**, and **Sentry Agent Tracing** among others. Use Gemma when it actually handles image reasoning well, Atlas if it best fits the backend, and Render if hosting terms work. Sentry Agent Tracing is optional only if genuine model tracing is implemented. Partner involvement is **secondary** to experience and correctness; document precisely what each partner technology does, and claim prize categories only if genuinely used. Verify any partner promotion independently before budgeting for it.

## 16. Definition of Done and handoff deliverables

- Running Next.js website, **FastAPI API** (with `/docs`, `/openapi.json`, and `/health`), durable Python job processor, and real AI inference with environment templates and reproducible deployment instructions.
- Seed script for species/requirements/packs/badges and two demo users (development only).
- `README.md`: elevator pitch, quick start, architecture, provider credentials setup, model selection and benchmark, limitations, outdoors test evidence, screenshots and demo links.
- FastAPI-generated OpenAPI documentation and typed frontend client, pytest tests with recorded results, MongoDB seed/index script.
- `IMPLEMENTATION_STATUS.md` with real feature status; no unsupported "completed" claims.
- Demo script: Quick Capture -> Timed Hunt -> Friend Challenge with two accounts -> Pack completion -> Friends/Global leaderboard -> share summary.
- DEV submission write-up: problem, why open-source AI is central, what was implemented, real-world experience, exact partner tech use, limitations and lessons.

**Product sentence:** *Collect wildlife discoveries, challenge friends, complete ecosystems, and earn rewards for exploring the world instead of staring at your screen.*
