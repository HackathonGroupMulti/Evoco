# INSTRUCTIONS

This file is the durable working memory for this repository across chat windows.

## Objective

Build a technically strong Amazon Nova hackathon project with a backend-first strategy.

## Working Rules

1. Update this file after meaningful progress.
2. Capture decisions with short rationale.
3. Keep entries concise and actionable.
4. Prefer append-only updates to preserve history.

## Context Saving In Chat Windows

Use this checklist before ending any chat session:

1. Update `Current Goal`.
2. Move finished items into `Completed`.
3. List exactly three `Next Tasks`.
4. Record blockers and assumptions.
5. Add runnable commands used for validation.

## Chat Handoff Snapshot

Date: 2026-02-10
Current Goal: Build the React frontend to connect to the backend.
Completed:
- Repository was reduced to core docs only.
- Project direction selected: backend-first architecture.
- Full backend built: FastAPI + services + orchestration pipeline.
- Services: planner (Nova 2 Lite), executor (Nova Act), voice (Nova Sonic), output formatter.
- Orchestration pipeline with WebSocket live events.
- All 22 tests passing (planner, executor, pipeline, API).
- Mock fallback mode works without any API keys.
In Progress: (none)
Next 3 Tasks:
1. Build React frontend with task submission UI.
2. Add React Flow task graph visualization (connected to WS events).
3. Add voice input component (mic -> /api/voice).
Risks/Blockers:
- Need AWS credentials + Nova Act key for live mode (mock works fine).
Run Commands:
- `pip install -r backend/requirements.txt`
- `python -m uvicorn backend.main:app --reload` (port 8000)
- `python -m pytest backend/tests/ -v` (22 tests)

## Decision Log

### 2026-02-10
- Decision: Start backend before frontend.
- Why: The project differentiator is orchestration, retrieval, and safety logic.

## Session Notes Template

```md
### Session YYYY-MM-DD HH:MM
Goal:
Changes:
Validation:
Open Issues:
Next Step:
```
