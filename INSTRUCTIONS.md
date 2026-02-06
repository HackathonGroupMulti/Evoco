# Development Instructions

## Overview

Build a voice/text-controlled autonomous web agent using Amazon Nova. The agent receives natural language commands, plans multi-step workflows, executes them via browser automation, and returns structured results—all while visualizing the process in real-time.

---

## Scope

### In Scope (MVP)

- [ ] Text input for commands
- [ ] Voice input using Amazon Nova Sonic
- [ ] Task planning with Amazon Nova 2 Lite
- [ ] Browser automation with Amazon Nova Act
- [ ] Real-time task graph visualization
- [ ] Live status updates via WebSocket
- [ ] Structured results display (table format)
- [ ] CSV export of results
- [ ] Single demo use case: price comparison across 3 sites

### Out of Scope (Post-Hackathon)

- Multi-user authentication
- Persistent task history
- Custom site configurations
- Mobile app version
- Complex error recovery
- Multiple simultaneous agents

---

## Tech Stack

### Frontend
- **React 18** with TypeScript
- **React Flow** for task graph visualization
- **Tailwind CSS** for styling
- **Web Speech API** or Nova Sonic client for voice

### Backend
- **FastAPI** (Python 3.11+)
- **WebSockets** for real-time updates
- **Pydantic** for request/response schemas
- **boto3** for AWS SDK

### AWS Services
| Service | Purpose |
|---------|---------|
| Amazon Nova Sonic | Voice-to-text and text-to-speech |
| Amazon Nova 2 Lite | Task planning and reasoning |
| Amazon Nova Act | Browser automation |
| S3 | Store exported results (optional) |
| App Runner / ECS | Host backend |

---

## Architecture

### Data Flow

```
1. User Input (voice/text)
        │
        ▼
2. Backend receives command
        │
        ▼
3. Nova Sonic transcribes (if voice)
        │
        ▼
4. Nova Lite generates execution plan
        │
        ├──► Plan sent to frontend (WebSocket)
        │    └── Task graph renders
        ▼
5. Nova Act executes each step
        │
        ├──► Status updates sent (WebSocket)
        │    └── Graph nodes update
        ▼
6. Results aggregated
        │
        ├──► Results sent to frontend
        │    └── Table populates
        ▼
7. Nova Sonic speaks summary (optional)
```

### WebSocket Events

| Event | Direction | Payload |
|-------|-----------|---------|
| `command` | Client → Server | `{ text: string, isVoice: boolean }` |
| `plan` | Server → Client | `{ nodes: Node[], edges: Edge[] }` |
| `step_start` | Server → Client | `{ stepId: string }` |
| `step_complete` | Server → Client | `{ stepId: string, result: any }` |
| `step_error` | Server → Client | `{ stepId: string, error: string }` |
| `results` | Server → Client | `{ items: Product[], summary: string }` |
| `voice_response` | Server → Client | `{ audioUrl: string, text: string }` |

---

## Implementation Plan

### Phase 1: Foundation (Day 1)

#### Task 1.1: Project Setup
- [ ] Initialize React app with TypeScript and Tailwind
- [ ] Initialize FastAPI backend with project structure
- [ ] Set up WebSocket connection between frontend and backend
- [ ] Verify bidirectional communication works

#### Task 1.2: Basic UI Shell
- [ ] Create layout: input panel (left), graph area (center), results (right)
- [ ] Build text input component with submit button
- [ ] Build placeholder task graph area
- [ ] Build placeholder results panel

#### Task 1.3: Backend Skeleton
- [ ] Create FastAPI app with WebSocket endpoint
- [ ] Define Pydantic schemas for all events
- [ ] Create stub functions for planner/executor
- [ ] Test with hardcoded responses

---

### Phase 2: Planning Engine (Day 1-2)

#### Task 2.1: Nova Lite Integration
- [ ] Set up AWS credentials and boto3 client
- [ ] Create planning prompt template
- [ ] Implement `generate_plan()` function
- [ ] Parse LLM output into structured plan

#### Task 2.2: Plan Schema
```python
class PlanStep(BaseModel):
    id: str
    action: str  # "navigate", "extract", "compare"
    target: str  # URL or selector
    description: str
    depends_on: list[str] = []

class ExecutionPlan(BaseModel):
    task_summary: str
    steps: list[PlanStep]
```

#### Task 2.3: Planning Prompt
```
You are a web automation planner. Given a user task, generate a step-by-step plan.

User task: {user_input}

Output a JSON plan with steps. Each step has:
- id: unique identifier
- action: one of [navigate, extract, compare, summarize]
- target: URL or data reference
- description: what this step does
- depends_on: list of step IDs that must complete first

Available sites for price comparison:
- Amazon: https://www.amazon.com/s?k={query}
- Best Buy: https://www.bestbuy.com/site/searchpage.jsp?st={query}
- Newegg: https://www.newegg.com/p/pl?d={query}
```

---

### Phase 3: Execution Engine (Day 2)

#### Task 3.1: Nova Act Integration
- [ ] Set up Nova Act client
- [ ] Create `execute_step()` function
- [ ] Handle navigation actions
- [ ] Handle extraction actions

#### Task 3.2: Extraction Schema
```python
class Product(BaseModel):
    name: str
    price: float
    url: str
    source: str  # "amazon", "bestbuy", "newegg"
    image_url: str | None = None
    rating: float | None = None
```

#### Task 3.3: Step Execution Loop
```python
async def execute_plan(plan: ExecutionPlan, ws: WebSocket):
    results = {}

    for step in topological_sort(plan.steps):
        await ws.send_json({"event": "step_start", "stepId": step.id})

        try:
            result = await execute_step(step, results)
            results[step.id] = result
            await ws.send_json({
                "event": "step_complete",
                "stepId": step.id,
                "result": result
            })
        except Exception as e:
            await ws.send_json({
                "event": "step_error",
                "stepId": step.id,
                "error": str(e)
            })
```

---

### Phase 4: Visualization (Day 2-3)

#### Task 4.1: Task Graph Component
- [ ] Install and configure React Flow
- [ ] Convert plan to React Flow nodes/edges
- [ ] Style nodes by status (pending, running, complete, error)
- [ ] Add smooth animations for status changes

#### Task 4.2: Node Styling
```typescript
const nodeStyles = {
  pending: { background: '#374151', border: '1px solid #4B5563' },
  running: { background: '#1E40AF', border: '2px solid #3B82F6', animation: 'pulse' },
  complete: { background: '#065F46', border: '1px solid #10B981' },
  error: { background: '#991B1B', border: '1px solid #EF4444' }
};
```

#### Task 4.3: Results Panel
- [ ] Build data table component
- [ ] Add sorting by price/rating
- [ ] Highlight best value row
- [ ] Add CSV export button

---

### Phase 5: Voice Integration (Day 3)

#### Task 5.1: Voice Input
- [ ] Add microphone button to input panel
- [ ] Capture audio from browser
- [ ] Send audio to backend
- [ ] Transcribe with Nova Sonic
- [ ] Return text and trigger planning

#### Task 5.2: Voice Output
- [ ] Generate summary text after execution
- [ ] Convert to speech with Nova Sonic
- [ ] Play audio response in browser

#### Task 5.3: Voice UX
- [ ] Add visual indicator when listening
- [ ] Add visual indicator when agent is speaking
- [ ] Handle microphone permissions gracefully

---

### Phase 6: Polish (Day 3-4)

#### Task 6.1: Error Handling
- [ ] Handle network errors gracefully
- [ ] Show user-friendly error messages
- [ ] Add retry button for failed steps

#### Task 6.2: Demo Reliability
- [ ] Test full flow 10+ times
- [ ] Identify and fix flaky points
- [ ] Add fallback for Nova Act failures (cached results)

#### Task 6.3: Visual Polish
- [ ] Add loading states
- [ ] Smooth transitions
- [ ] Mobile-responsive layout (optional)

---

## File Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── InputPanel/
│   │   │   ├── InputPanel.tsx
│   │   │   ├── TextInput.tsx
│   │   │   └── VoiceButton.tsx
│   │   ├── TaskGraph/
│   │   │   ├── TaskGraph.tsx
│   │   │   ├── PlanNode.tsx
│   │   │   └── useGraphLayout.ts
│   │   ├── ResultsPanel/
│   │   │   ├── ResultsPanel.tsx
│   │   │   ├── ProductTable.tsx
│   │   │   └── ExportButton.tsx
│   │   └── StatusBar/
│   │       └── StatusBar.tsx
│   ├── hooks/
│   │   ├── useWebSocket.ts
│   │   ├── useVoice.ts
│   │   └── usePlan.ts
│   ├── types/
│   │   └── index.ts
│   ├── App.tsx
│   └── main.tsx
├── package.json
├── tailwind.config.js
└── tsconfig.json

backend/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app, WebSocket endpoint
│   ├── planner.py        # Nova Lite integration
│   ├── executor.py       # Nova Act integration
│   ├── voice.py          # Nova Sonic integration
│   ├── schemas.py        # Pydantic models
│   └── config.py         # AWS config, environment variables
├── requirements.txt
└── Dockerfile
```

---

## API Reference

### WebSocket Endpoint

```
WS /ws
```

### REST Endpoints (optional, for testing)

```
POST /api/plan
Body: { "command": "Find laptops under $800" }
Response: { "plan": ExecutionPlan }

POST /api/execute
Body: { "plan": ExecutionPlan }
Response: { "results": Product[] }
```

---

## Environment Variables

```env
# AWS
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1

# Nova
NOVA_SONIC_MODEL_ID=amazon.nova-sonic-v1:0
NOVA_LITE_MODEL_ID=amazon.nova-lite-v1:0

# App
ENVIRONMENT=development
LOG_LEVEL=INFO
```

---

## Demo Script

### Setup (before demo)
1. Open browser to app URL
2. Test microphone permissions
3. Have backup command ready to paste

### Demo Flow (90 seconds)

**[0:00]** "This is Nova Agent — an autonomous AI that executes real web tasks."

**[0:10]** *Click mic button, speak:* "Find me the best laptop under $800"

**[0:15]** *Agent responds:* "I'll search Amazon, Best Buy, and Newegg for laptops under $800."

**[0:20]** *Task graph appears with 3 parallel branches*

**[0:25]** "Watch as the agent executes each step in real-time."

**[0:30-0:60]** *Nodes light up as execution progresses. Results populate in table.*

**[0:65]** *Agent speaks:* "Found 15 laptops. Best value is the Lenovo IdeaPad 3 at $549 with 4.5 stars."

**[0:75]** "I can export these results..." *Click CSV export*

**[0:80]** "The agent used three Nova models: Sonic for voice, Lite for planning, and Act for browser automation."

**[0:90]** "Questions?"

---

## Judging Criteria Alignment

| Criteria | How We Address It |
|----------|-------------------|
| **Technical Implementation (60%)** | Multi-model orchestration, real browser automation, WebSocket streaming, structured extraction |
| **Innovation (20%)** | Visual agent transparency (task graph), voice-first UX, watchable AI |
| **AWS Service Usage (20%)** | Nova Sonic + Nova Lite + Nova Act + optional S3/App Runner |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Nova Act rate limits | Cache successful extractions, limit demo to 3 sites |
| Sites block automation | Use well-known user agents, add delays |
| Voice recognition fails | Always have text input as fallback |
| Demo flakiness | Pre-cache one successful run as fallback |

---

## Timeline

| Day | Focus | Deliverable |
|-----|-------|-------------|
| 1 | Foundation + Planning | Working WebSocket, text input, plan generation |
| 2 | Execution + Graph | Nova Act executing steps, graph updating live |
| 3 | Voice + Polish | Voice I/O working, smooth demo flow |
| 4 | Testing + Buffer | 10+ successful demo runs, fix edge cases |

---

## Commands

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Docker (production)
```bash
docker-compose up --build
```
