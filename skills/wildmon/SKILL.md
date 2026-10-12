---
name: wildmon
description: Build or maintain Wildmon, the nature discovery web game in this repository. Applies to frontend, FastAPI, AI inference, scoring, and deployment work here only.
---

# Wildmon

Read `README.md` for the product overview and inspect the current code for behavior and limitations. Resolve conflicts in favor of explicit user instructions.

## Stack and boundaries

- `apps/web`: Next.js App Router, TypeScript, pnpm, Tailwind CSS, Radix primitives, Geist font and design language with a joyful nature palette. Run the Vercel React best practices and design-taste frontend skills for frontend work. Keep pages server rendered where useful and isolate interactive client components.
- `apps/api`: Python 3.12+, `uv`, `fastapi[standard]`, Pydantic v2, PyMongo `AsyncMongoClient`, and a replaceable Gemma vision adapter. Use LangChain only where it adds a clear orchestration step, such as prompt, model, parser, and retry composition. FastAPI alone owns authentication, discovery state, XP, rules, and authorization.
- Generate frontend API types from FastAPI OpenAPI. Do not hand-maintain duplicate domain schemas when generation is practical.
- Keep AI errors and uncertainty visible. Never present fixtures or untested inference as a live model result.

## Code quality

- Use focused domain modules and pure functions for matching and scoring. Keep FastAPI route handlers thin.
- Add Python docstrings to complex functions, classes, and methods, explaining invariants and edge cases. Avoid comments that repeat obvious code.
- Use typed request/response schemas and explicit MongoDB indexes. Make rewards, worker claims, and challenge transitions idempotent.
- Use a Prettier config based on the Airbnb style (single quotes, trailing commas, 100-character print width) for frontend files. Use Ruff for Python.
- Keep tests and user-facing documentation aligned with shipped behavior. Do not claim that unverified inference or product flows have been tested.
