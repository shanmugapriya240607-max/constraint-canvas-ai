# ConstraintCanvas AI

> **AI-Powered Natural-Language Planning & Constraint Optimization Engine**

ConstraintCanvas AI converts unstructured natural-language planning requirements into mathematically optimal, feasible, and prioritized schedules. It combines ChatGPT structured data extraction, strict Pydantic validation, deterministic graph priority analysis, Google OR-Tools CP-SAT constraint optimization, SQLite history persistence, and dynamic React visualizations (Table, Gantt Chart, Execution Timeline).

---

## 📌 Problem Statement

Real-world scheduling problems involve complex dependencies ("B must happen after A"), fixed deadlines ("finish before 9:00 AM"), resource limits ("only one person available"), and variable task durations. When users describe their schedules in natural prose, traditional calendar apps fail to parse constraints, calculate critical paths, or generate mathematically valid execution orderings.

---

## 💡 Proposed Solution

ConstraintCanvas AI provides a full-stack, end-to-end intelligent scheduling pipeline:

```text
User Text → ChatGPT Extraction → Pydantic Validation → Priority Engine → OR-Tools Optimization → SQLite Storage → Visual Schedule
```

1. **ChatGPT Extraction**: Translates natural prose into structured planning components (tasks, durations, deadlines, dependencies, resources, objectives).
2. **Pydantic Validation**: Enforces strict typing, time formats (`HH:MM`), positive durations, and unique task IDs.
3. **Deterministic Validation**: Graph-based checks (Kahn's/DFS algorithm) detecting circular dependencies, self-dependencies, unknown references, and missing data.
4. **Priority Engine**: Computes topological execution levels, downstream impact, and 0–100 Priority Scores using a 50/30/20 formula.
5. **Google OR-Tools CP-SAT**: Solves exact integer time variables (`0..1439` minutes) under hard dependencies, deadlines, and resource non-overlap constraints.
6. **SQLite Persistence**: Automatically records every solve run to database for audit history and reloading.
7. **React Visualization**: Displays schedule through a summary card, responsive schedule table, dynamic Gantt chart, and task timeline.

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend** | React 18, Vite 5, Plain JavaScript (ES Modules), Vanilla CSS |
| **Backend** | Python 3.10+, FastAPI, Uvicorn |
| **Intelligence** | OpenAI Python SDK (Structured Outputs via `beta.chat.completions.parse`) |
| **Validation** | Pydantic v2 |
| **Optimization** | Google OR-Tools CP-SAT |
| **Database** | SQLite + SQLAlchemy ORM |
| **Testing** | Pytest, FastAPI TestClient, Mocking |

---

## 📁 Directory Structure

```text
constraint-canvas-ai/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app, endpoints (/api/health, /api/solve, /api/history)
│   │   ├── schemas.py           # Pydantic models (PlanningRequest, Task, ExtractedProblem, SolveResponse)
│   │   ├── ai_parser.py         # OpenAI SDK client & Structured Output prompt
│   │   ├── validator.py         # 24-hour time utilities & graph circular dependency detection
│   │   ├── priority_engine.py   # Topological execution levels & 50/30/20 priority scoring
│   │   ├── solver.py            # Google OR-Tools CP-SAT scheduling solver
│   │   └── database.py          # SQLite engine, SessionLocal, SolveRun ORM model
│   ├── data/
│   │   └── .gitkeep             # Preserves database directory
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_ai_parser.py    # OpenAI parser & endpoint unit tests
│   │   ├── test_validator.py    # Time conversion & deterministic validation tests
│   │   ├── test_solver.py       # OR-Tools scheduling & Office example tests
│   │   └── test_database.py     # SQLite persistence & history endpoint tests
│   ├── .env.example
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ProblemInput.jsx # Input textarea, Dual example controls, character counter
│   │   │   ├── PipelineView.jsx # Architecture processing pipeline visualization
│   │   │   ├── RecentPlans.jsx  # SQLite history sidebar & detail loader
│   │   │   ├── LoadingState.jsx # Dynamic 5-step pipeline progress spinner
│   │   │   ├── ExtractedData.jsx# Summary metrics card (confidence %, makespan, window)
│   │   │   ├── ResultTable.jsx  # Responsive schedule table with badges & sorting
│   │   │   ├── GanttChart.jsx   # Dynamic Gantt chart calculated from API start/end times
│   │   │   ├── TaskTimeline.jsx # Sequential/parallel execution timeline cards
│   │   │   └── ErrorMessage.jsx # Explicit status error handling (NEEDS_INPUT, INVALID, INFEASIBLE)
│   │   ├── api.js               # Centralized fetch API calls with timeouts
│   │   ├── App.jsx              # Main workspace layout & status indicators
│   │   ├── main.jsx             # React entry point
│   │   └── styles.css           # Dark theme design system & CSS Grid Gantt styling
│   ├── .env.example
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
│
├── .gitignore
├── PROJECT_SPEC.md
└── README.md
```

---

## ⚡ Quick Start & Running Instructions

### Prerequisites
- **Python**: Version 3.10 or higher
- **Node.js**: Version 18.0 or higher
- **Git**

### 1. Environment Setup

Copy example environment files:

```bash
# Backend environment template
cp backend/.env.example backend/.env

# Frontend environment template
cp frontend/.env.example frontend/.env
```

Edit `backend/.env` to configure parser mode and API settings:

```env
# Parser Mode: 'offline' (deterministic NLP fallback for hackathon demo) or 'openai'
PARSER_MODE=offline

OPENAI_API_KEY=your_actual_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
DATABASE_URL=sqlite:///./data/constraint_canvas.db
FRONTEND_ORIGIN=http://localhost:5173
```

> **Emergency Offline Demo Mode**: When `PARSER_MODE=offline` is set (or if OpenAI API quota is exhausted), ConstraintCanvas AI transparently switches to deterministic natural-language rule-based parsing (`parser_mode="OFFLINE_RULES"`). The system extracts tasks, converts hours to minutes, parses deadlines (`9:00 AM` -> `09:00`, `6:00 PM` -> `18:00`), and determines dependencies (`A before B`, `B after A`, `A then B`) without making external API calls. All extracted tasks still pass through Pydantic validation, deterministic constraint checks, topological priority scoring, OR-Tools CP-SAT optimization, and SQLite persistence.

> **Security Note**: Never commit `backend/.env` or exposure of real API keys to version control. `.env` and `*.db` are strictly ignored by `.gitignore`.

### 2. Backend Startup

```bash
# Navigate to backend directory
cd backend

# Create & activate virtual environment (optional)
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI server on port 8000
uvicorn app.main:app --reload --port 8000
```

The backend server runs at `http://localhost:8000`. API documentation is accessible at `http://localhost:8000/docs`.

### 3. Frontend Startup

```bash
# Navigate to frontend directory in a new terminal
cd frontend

# Install Node dependencies
npm install

# Start Vite development server on port 5173
npm run dev
```

Open your browser at `http://localhost:5173`.

---

## 🛰️ API Documentation

### `GET /api/health`
Checks backend service availability.

**Response:**
```json
{
  "status": "healthy",
  "openai_configured": true,
  "database": "connected",
  "optimizer": "available"
}
```

### `POST /api/solve`
Processes natural language text through ChatGPT extraction, validation, priority engine, and OR-Tools solver.

**Request:**
```json
{
  "text": "Tomorrow I must reach the office by 9:00 AM. Waking up takes 5 minutes. After waking up, I need to get ready for 30 minutes. After getting ready, I need to eat breakfast for 20 minutes. After breakfast, I need to travel to the office for 40 minutes. Travel must finish by 9:00 AM."
}
```

**Successful Response (`status: "OPTIMAL"`):**
```json
{
  "status": "OPTIMAL",
  "problem_title": "Morning office schedule",
  "objective": { "type": "LATEST_START", "description": "Start morning routine as late as possible" },
  "extraction_confidence": 0.95,
  "makespan_minutes": 540,
  "tasks": [
    {
      "id": "task_1",
      "name": "Wake up",
      "duration_minutes": 5,
      "start": "07:25",
      "end": "07:30",
      "depends_on": [],
      "execution_level": 1,
      "priority_score": 70,
      "priority_reason": "This task unlocks 3 dependent tasks, belongs to the critical path.",
      "is_critical": true,
      "is_passive": false,
      "resources": ["person"]
    },
    {
      "id": "task_2",
      "name": "Get ready",
      "duration_minutes": 30,
      "start": "07:30",
      "end": "08:00",
      "depends_on": ["task_1"],
      "execution_level": 2,
      "priority_score": 53,
      "priority_reason": "This task unlocks 2 dependent tasks, belongs to the critical path.",
      "is_critical": true,
      "is_passive": false,
      "resources": ["person"]
    },
    {
      "id": "task_3",
      "name": "Eat breakfast",
      "duration_minutes": 20,
      "start": "08:00",
      "end": "08:20",
      "depends_on": ["task_2"],
      "execution_level": 3,
      "priority_score": 37,
      "priority_reason": "This task unlocks 1 dependent task, belongs to the critical path.",
      "is_critical": true,
      "is_passive": false,
      "resources": ["person"]
    },
    {
      "id": "task_4",
      "name": "Travel to office",
      "duration_minutes": 40,
      "start": "08:20",
      "end": "09:00",
      "depends_on": ["task_3"],
      "execution_level": 4,
      "priority_score": 50,
      "priority_reason": "This task final execution task, belongs to the critical path, has fixed deadline 09:00.",
      "is_critical": true,
      "is_passive": false,
      "resources": ["person"]
    }
  ],
  "explanation": "Successfully generated optimal schedule for 4 tasks satisfying all constraints."
}
```

### `GET /api/history`
Returns recent solve history records (newest first, max 50).

### `GET /api/history/{run_id}`
Returns complete details and parsed JSON objects for a specific solve run ID.

---

## 🧠 Core Component Explanations

### 1. ChatGPT Structured Data Extraction
Uses `client.beta.chat.completions.parse` with `response_format=ExtractedProblem`. The AI identifies problem title, optimization objective (`MINIMIZE_MAKESPAN`, `EARLIEST_FINISH`, `LATEST_START`), tasks, explicit durations, earliest start times, deadlines, and dependencies without calculating schedules or inventing missing numerical values.

### 2. Pydantic & Deterministic Validation
- **Pydantic**: Validates 24-hour `HH:MM` time regex (`^([0-1][0-9]|2[0-3]):[0-5][0-9]$`), positive integer durations, non-empty IDs, and confidence scores `[0.0, 1.0]`.
- **Graph Validation**: Uses Depth-First Search (DFS) graph traversal to detect circular dependencies (`CIRCULAR_DEPENDENCY`), self-dependencies (`SELF_DEPENDENCY`), and unknown task references (`UNKNOWN_DEPENDENCY`).
- **Missing Data Handling**: If any task duration is unstated, returns `status: "NEEDS_INPUT"` with clarification questions.

### 3. Priority Engine
Calculates execution priority for display and tie-breaking using the 50/30/20 rule:
$$\text{Priority Score} = 50\% \text{ downstream impact} + 30\% \text{ deadline urgency} + 20\% \text{ critical path status}$$
Topological execution levels (Level 1, Level 2...) dictate execution order; hard dependencies always override numerical scores.

### 4. Google OR-Tools CP-SAT Solver
Maps tasks into integer start/end variables on a `0..1439` minute horizon. Enforces:
- Dependency bounds: $e_{\text{predecessor}} \le s_{\text{successor}}$
- Deadlines & Earliest Starts: $s_{\text{task}} \ge \text{start}_{\min}$, $e_{\text{task}} \le \text{deadline}_{\min}$
- Resource Non-Overlap: `model.AddNoOverlap` for active `person` tasks.
- `LATEST_START`: Maximizes schedule start time while satisfying final deadlines.

### 5. SQLite Persistence & History
Every completed solve (`OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `INVALID`, `NEEDS_INPUT`) is safely persisted to `solve_runs` table in SQLite. Users can browse past plans and reload saved results directly into the workspace.

---

## ⚠️ Error Handling Matrix

| Scenario | Status Code / Response | UI Display Behavior |
| :--- | :--- | :--- |
| Empty Input | `HTTP 400 Bad Request` | Red error card: "Planning text is required." |
| Missing Durations | `HTTP 200 NEEDS_INPUT` | Yellow card: Lists clarification questions & "Edit requirement" button |
| Invalid Constraints | `HTTP 200 INVALID` | Red card: Displays error code, affected task IDs, and suggestions |
| Deadline Impossible | `HTTP 200 INFEASIBLE` | Red card: Displays "No feasible schedule found" & solver explanation |
| OpenAI Gateway Failure | `HTTP 502 Bad Gateway` | Red card: Safe error message without exposing API keys |
| Server Exception | `HTTP 500 Internal Error` | Red card: Generic message without exposing internal stack traces |

---

## 🧪 Testing & Verification

### Backend Automated Unit Tests (`pytest`)

Run all 27 automated tests:

```bash
cd backend
python -m pytest -v
```

All 27 test cases pass cleanly without requiring real OpenAI API calls or internet access.

### Frontend Production Build

Verify Vite production build compilation:

```bash
cd frontend
npm run build
```

---

## 🎪 Hackathon Demo Walkthrough Flow

1. Open `http://localhost:5173` — Observe healthy status badges (ChatGPT, Pydantic, OR-Tools, SQLite).
2. Click **Office Example** — Observe auto-populated text.
3. Click **Analyze & Optimize** — Watch the dynamic 5-step pipeline loading spinner.
4. Review Schedule — Inspect summary metrics, dynamic Gantt chart (`07:25–09:00`), schedule table, and execution timeline.
5. Check Recent Plans — Confirm the run is persisted in SQLite and listed under Recent Plans.
6. Click **Study Session Example** — Observe `EARLIEST_FINISH` optimization.
7. Click a saved item in Recent Plans — Reload previous run state into the workspace.

---

## 🔮 Limitations & Future Improvements

- **Current Limitation**: Horizon is limited to single-day 24-hour schedules (`00:00` to `23:59`).
- **Future Improvement**: Multi-day scheduling horizon support and calendar export (iCal / Google Calendar).
- **Future Improvement**: Multi-person team resource allocation and interactive Gantt drag-and-drop adjustments.

---

## 🔐 Security Notice

This project strictly enforces repository safety. Secrets, `.env` files, API keys, SQLite `.db` databases, `node_modules`, `dist` build folders, and Python cache files are ignored via `.gitignore` and must never be committed.
