# Evoco Control Panel

A voice and text-controlled autonomous web agent powered by Amazon Nova.

Built for the Amazon Nova Hackathon.

## What It Does

This is not a chatbot. It is an operator console for an AI worker.

`Voice/Text Command -> Agent Plans -> Browser Executes -> Structured Results`

Example prompt:
"Find me the best laptop under $800 from Amazon, Best Buy, and Newegg."

## Key Features

- Voice input with Amazon Nova Sonic.
- Visual task graph for plan transparency.
- Live execution updates.
- Browser automation via Amazon Nova Act.
- Structured outputs (CSV, JSON, summary).

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React, Three.js / React Flow |
| Backend | FastAPI (Python) |
| Voice | Amazon Nova Sonic |
| Planning | Amazon Nova 2 Lite |
| Execution | Amazon Nova Act |
| Infrastructure | AWS (App Runner / ECS) |

## Context Saving In Chat Windows

Use `INSTRUCTIONS.md` as the durable handoff file between chat windows.

Workflow:
1. Update `INSTRUCTIONS.md` after each meaningful change.
2. Keep a current `Chat Handoff Snapshot` block in `INSTRUCTIONS.md`.
3. In a new chat window, paste that snapshot first, then state one immediate objective.
4. Reference changed file paths so work can continue without re-discovery.

Handoff template:

```md
## Chat Handoff Snapshot
Date: YYYY-MM-DD
Current Goal:
Completed:
In Progress:
Next 3 Tasks:
Risks/Blockers:
Run Commands:
```

## Project Structure

```text
frontend/                # React app
backend/                 # FastAPI app
INSTRUCTIONS.md          # Durable working context
README.md
```

## Getting Started

See `INSTRUCTIONS.md` for workflow and handoff conventions.

## License

MIT
