# Evoco Control Panel

**A voice and text-controlled autonomous web agent powered by Amazon Nova.**

Built for the **Amazon Nova AI Hackathon**.

> This is not a chatbot. It is an operator console for an AI worker.

```
Voice/Text Command --> Agent Plans --> Browsers Execute in Parallel --> Structured Results
```

**Example**: *"Find me the best laptop under $800 from Amazon, Best Buy, and Newegg."*

Evoco decomposes that into a DAG of parallel browser agents, dispatches them simultaneously, extracts structured data from each site, then uses an LLM to compare, rank, and summarize — all with a live visual graph updating in real time.

---

## Demo

```
  ┌──────────────────────────────────────────────────────────────────────────┐
  │  EVOCO CONTROL PANEL                              [Graph] [Timeline]    │
  │                                                                         │
  │  ┌─ Command ──────┐  ┌─ Live Task Graph ──────────────┐  ┌─ Results ─┐ │
  │  │                 │  │                                │  │           │ │
  │  │ > Find me the   │  │   [Amazon]─┐                   │  │  1. ASUS  │ │
  │  │   best laptop   │  │   [BestBuy]┼─>[Compare]─>[Sum] │  │  2. HP    │ │
  │  │   under $800... │  │   [Newegg]─┘                   │  │  3. Dell  │ │
  │  │                 │  │                                │  │           │ │
  │  │  History:       │  │   Steps: 8/11  Cost: $0.018    │  │  $0.018   │ │
  │  │  - laptops...   │  │                                │  │  7.2s     │ │
  │  └─────────────────┘  └────────────────────────────────┘  └───────────┘ │
  │  [EXECUTING] ████████████░░░ 8/11 steps | $0.018 | Mock Mode            │
  └──────────────────────────────────────────────────────────────────────────┘
```

Three-panel layout: command input + history (left), live DAG visualization (center), structured results (right).

---

## Key Features

- **Multi-model orchestration** — 3 Amazon Nova models working together (Sonic + Lite + Act)
- **DAG-based parallel execution** — independent site branches run concurrently, not sequentially
- **Voice input** — Amazon Nova Sonic with real-time streaming transcription
- **Live task graph** — React Flow visualization updates in real time via WebSocket
- **Structured extraction** — schema-validated JSON from browser agents, not free text
- **Adaptive resilience** — step-level retry, branch isolation, and LLM-driven re-planning on failure
- **Browser session pool** — bounded concurrency with semaphore-controlled session reuse
- **Multi-format output** — JSON, CSV, or natural language summary
- **Cost tracking** — per-step cost estimation with full timing waterfall trace
- **Mock fallback** — fully functional demo mode without any API keys

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React + TypeScript)                │
│                                                                      │
│   Voice Orb ──┐                                                      │
│                ├── WebSocket ──> Live DAG Graph (React Flow)          │
│   Command Bar ┘                 Waterfall Timeline                   │
│                                 Results Panel + Cost Badge           │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────────┐
│                        BACKEND (FastAPI + Python)                    │
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐   │
│   │                   ORCHESTRATION PIPELINE                     │   │
│   │                                                              │   │
│   │   Voice ──> Planner ──> DAG Builder ──> Parallel Runner      │   │
│   │   (Sonic)   (Nova Lite)  (dependency     (asyncio.wait +     │   │
│   │                          graph)           FIRST_COMPLETED)   │   │
│   │                                                │             │   │
│   │                    ┌───────────┬───────────────┤             │   │
│   │                    ▼           ▼               ▼             │   │
│   │             Browser Exec  Browser Exec   LLM Executor       │   │
│   │             (Nova Act)    (Nova Act)     (Nova 2 Lite)       │   │
│   │             amazon.com    bestbuy.com    compare, rank,      │   │
│   │             Pool slot 1   Pool slot 2    summarize           │   │
│   │                    │           │               │             │   │
│   │                    ▼           ▼               ▼             │   │
│   │              Result Parser (4-strategy fallback)             │   │
│   │              schema validate > json > regex > LLM repair     │   │
│   │                              │                               │   │
│   │                    Output Formatter + Cost Tracker            │   │
│   │                    JSON / CSV / Summary                       │   │
│   └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│   Browser Pool (semaphore)  |  Retry + Re-plan Engine                │
└──────────────────────────────────────────────────────────────────────┘
```

### Pipeline Stages

| Stage | What Happens | Model |
|-------|-------------|-------|
| 1. Planning | Decompose command into a DAG of steps with dependency edges | Nova 2 Lite |
| 2. Execution | Run independent branches in parallel, sequential within branches | Nova Act (browser) + Nova 2 Lite (reasoning) |
| 3. Degradation | Branch isolation, adaptive retry, LLM-driven re-planning | Nova 2 Lite |
| 4. Output | Format aggregated results as JSON, CSV, or summary | Local |
| 5. Observability | Per-step cost estimation, timing waterfall trace | Local |

### Execution Topology

```
                       ┌─ navigate Amazon ─ search ─ extract ──┐
command ─ plan (LLM) ──┤─ navigate BestBuy ─ search ─ extract ──┼─ compare (LLM) ─ summarize (LLM)
                       └─ navigate Newegg ─ search ─ extract ──┘
```

Site branches run **in parallel**. Steps within a branch run sequentially. LLM steps wait for all browser dependencies. A 3-site query runs in ~3.5 min wall-clock instead of ~10.5 min sequential — **O(1) vs O(N)** in the number of sites.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, Shadcn UI |
| Visualization | React Flow (DAG graph), custom waterfall timeline |
| Backend | FastAPI, Python, async/await, WebSocket |
| Voice | Amazon Nova Sonic (batch + streaming transcription) |
| Planning | Amazon Nova 2 Lite via Bedrock |
| Browser Automation | Amazon Nova Act SDK |
| Infrastructure | AWS Bedrock, App Runner / ECS ready |

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- (Optional) AWS credentials for live mode — works fully in mock mode without keys

### Install

```bash
# Backend
pip install -r backend/requirements.txt

# Frontend
cd frontend && npm install && cd ..

# Root (concurrently)
npm install
```

### Configure (Optional)

Copy `backend/.env.example` to `backend/.env` and fill in your keys:

```bash
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
NOVA_ACT_API_KEY=your_nova_act_key
```

Without these keys, everything runs in **mock mode** with deterministic plans, simulated browser results, and instant execution.

### Run

```bash
# Both frontend + backend together
npm run dev

# Or separately
npm run dev:backend    # FastAPI on port 8000
npm run dev:frontend   # Vite on port 5173
```

### Test

```bash
cd backend
python -m pytest tests/ -v
```

---

## API

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check with mode detection |
| `POST` | `/api/tasks` | Submit task (async, returns immediately) |
| `POST` | `/api/tasks/sync` | Submit task (waits for completion) |
| `GET` | `/api/tasks` | List recent tasks |
| `GET` | `/api/tasks/{id}` | Get task by ID |
| `GET` | `/api/tasks/{id}/result` | Get task output |
| `POST` | `/api/tasks/{id}/cancel` | Cancel a running task |
| `POST` | `/api/voice` | Upload audio for transcription |
| `GET` | `/api/logs` | Stream server logs (SSE) |

### WebSocket Endpoints

| Endpoint | Protocol |
|----------|----------|
| `/api/ws` | Send JSON command, receive live pipeline events |
| `/api/ws/voice` | Stream audio chunks, receive partial transcripts + pipeline events |

---

## Project Structure

```
Evoco/
├── backend/
│   ├── models/task.py              # TaskStep, TaskPlan, TaskResult, WSEvent
│   ├── orchestrator/
│   │   ├── dag.py                  # DAG parallel executor (asyncio.wait)
│   │   └── pipeline.py            # Full pipeline lifecycle + TaskStore
│   ├── routers/
│   │   ├── tasks.py               # REST task endpoints
│   │   ├── voice.py               # Voice upload endpoint
│   │   ├── ws.py                  # WebSocket handlers
│   │   └── logs.py                # Log streaming (SSE)
│   ├── services/
│   │   ├── planner.py             # Nova 2 Lite task decomposition
│   │   ├── executor.py            # Routes to Nova Act or LLM
│   │   ├── llm_executor.py        # Nova 2 Lite reasoning steps
│   │   ├── browser_pool.py        # Bounded browser session pool
│   │   ├── voice.py               # Nova Sonic transcription
│   │   ├── result_parser.py       # 4-strategy JSON parser
│   │   ├── output.py              # JSON/CSV/Summary formatter
│   │   ├── schemas.py             # Extraction schemas for act_get
│   │   ├── cost.py                # Cost estimation
│   │   └── log_store.py           # In-memory log ring buffer
│   ├── tests/                     # pytest suite
│   ├── config.py                  # Settings (pydantic-settings)
│   └── main.py                    # FastAPI entry point
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx                # Main 3-panel layout
│   │   ├── hooks/
│   │   │   ├── useTaskRunner.ts   # WebSocket task execution hook
│   │   │   └── useLogStream.ts    # WebSocket log streaming hook
│   │   ├── components/
│   │   │   ├── CommandPanel.tsx    # Command input + history
│   │   │   ├── TaskGraph.tsx      # React Flow DAG visualization
│   │   │   ├── WaterfallView.tsx  # Timing waterfall
│   │   │   ├── ResultsPanel.tsx   # Structured results display
│   │   │   ├── VoiceOrb.tsx       # Animated voice input
│   │   │   ├── ThinkingOverlay.tsx # Planning animation
│   │   │   ├── StatusBar.tsx      # Status + metrics bar
│   │   │   ├── LandingHero.tsx    # Landing page
│   │   │   └── LogPanel.tsx       # Server log viewer
│   │   └── types.ts               # TypeScript definitions
│   └── ...
│
├── COMPLEXITY.md                   # Architectural complexity plan
├── INSTRUCTIONS.md                 # Session handoff context
└── README.md
```

---

## Architectural Complexity

| Dimension | Approach |
|-----------|----------|
| **AI models orchestrated** | 3 (Nova Sonic + Nova 2 Lite + Nova Act) |
| **Execution topology** | DAG with parallel branches, not linear |
| **Concurrency** | asyncio.wait + FIRST_COMPLETED, semaphore-bounded pool |
| **State management** | Task lifecycle + browser sessions + result aggregation |
| **Resilience** | 3-layer: step retry with backoff, branch isolation, LLM re-planning |
| **Real-time feedback** | WebSocket event stream driving live graph updates |
| **Input modalities** | Voice (streaming) + Text |
| **Data flow** | Voice -> Plan -> Browser[] -> Aggregate -> LLM -> Structured Output |
| **Resource management** | Browser session pool with bounded concurrency |
| **Observability** | Per-step cost tracking + timing waterfall trace |
| **Output flexibility** | JSON, CSV, natural language summary |
| **Robustness** | 4-strategy result parser: schema -> json -> regex -> LLM repair |
| **Graceful degradation** | Full mock mode, partial results on branch failure |

---

## License

MIT
