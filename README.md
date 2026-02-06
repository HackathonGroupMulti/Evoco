# Evoco Control Panel

A voice and text-controlled autonomous web agent powered by Amazon Nova. Speak or type a task, watch the AI plan and execute it in real-time, and receive structured results.

Built for the **Amazon Nova Hackathon**.

## What It Does

This is not a chatbot. It's an **operator console for an AI worker**.

```
Voice/Text Command → Agent Plans → Browser Executes → Structured Results
```

Example:
> "Find me the best laptop under $800 from Amazon, Best Buy, and Newegg"

The agent will:
1. Parse your intent
2. Generate a multi-step plan (visible as a task graph)
3. Execute browser automation on each site
4. Extract and compare results
5. Return a structured comparison + recommendation

You watch it happen in real-time.

## Key Features

- **Voice Input** — Speak commands using Amazon Nova Sonic
- **Visual Task Graph** — See the agent's plan as an interactive node graph
- **Live Execution** — Watch progress as each step completes
- **Browser Automation** — Real web interactions via Amazon Nova Act
- **Structured Output** — Results exported as CSV, JSON, or summary

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React, Three.js / React Flow |
| Backend | FastAPI (Python) |
| Voice | Amazon Nova Sonic |
| Planning | Amazon Nova 2 Lite |
| Execution | Amazon Nova Act |
| Infrastructure | AWS (App Runner / ECS) |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │ Voice/Text  │  │   Task Graph    │  │   Results Panel     │  │
│  │   Input     │  │  (React Flow)   │  │   (Table/Export)    │  │
│  └─────────────┘  └─────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BACKEND (FastAPI)                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │   Voice     │  │    Planner      │  │    Executor         │  │
│  │  (Sonic)    │  │   (Nova Lite)   │  │   (Nova Act)        │  │
│  └─────────────┘  └─────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         AWS SERVICES                            │
├─────────────────────────────────────────────────────────────────┤
│  Amazon Nova Sonic │ Amazon Nova 2 Lite │ Amazon Nova Act      │
│  S3 (results)      │ CloudWatch (logs)  │ App Runner (hosting) │
└─────────────────────────────────────────────────────────────────┘
```

## Demo Scenario

**Primary demo: Price Comparison Agent**

1. User speaks: "Find laptops under $800"
2. Agent responds: "I'll check Amazon, Best Buy, and Newegg"
3. Task graph renders with 3 parallel branches
4. Each node lights up as execution progresses
5. Results table populates in real-time
6. Agent speaks: "Found 12 options. Best value is the Lenovo IdeaPad at $649"
7. User exports to CSV

**Duration:** 60-90 seconds

## Project Structure

```
├── frontend/                # React application
│   ├── src/
│   │   ├── components/
│   │   │   ├── VoiceInput/      # Mic button + speech handling
│   │   │   ├── TaskGraph/       # React Flow visualization
│   │   │   ├── ResultsPanel/    # Data table + export
│   │   │   └── StatusBar/       # Agent status display
│   │   ├── hooks/               # WebSocket, voice hooks
│   │   └── App.tsx
│   └── package.json
│
├── backend/                 # FastAPI server
│   ├── app/
│   │   ├── main.py              # FastAPI app + WebSocket
│   │   ├── planner.py           # Nova Lite planning logic
│   │   ├── executor.py          # Nova Act browser automation
│   │   ├── voice.py             # Nova Sonic integration
│   │   └── schemas.py           # Pydantic models
│   └── requirements.txt
│
├── INSTRUCTIONS.md          # Development guide
└── README.md
```

## Getting Started

See [INSTRUCTIONS.md](INSTRUCTIONS.md) for setup and development guide.

## Resume Bullets

This project demonstrates:

- Autonomous agent architecture with planning and execution loops
- Browser automation using Amazon Nova Act
- Voice interface integration with Amazon Nova Sonic
- Real-time WebSocket communication for live status updates
- Visual task graph rendering for agent transparency
- Multi-model orchestration (Sonic → Lite → Act)

## License

MIT
