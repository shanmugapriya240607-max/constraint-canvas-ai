# ConstraintCanvas AI

AI-powered planning assistant that converts natural-language problem descriptions into optimized schedules using OpenAI extraction and Google OR-Tools constraint solving.

ChatGPT extracts structured tasks and dependencies from natural language. Pydantic validates the extracted structure. Deterministic Python rules verify dependency correctness. Google OR-Tools performs scheduling optimization. SQLite stores solve history. React presents the result through a table, Gantt chart and timeline.

## Technology Stack

* **Frontend**: React + Vite using plain JavaScript
* **Backend**: Python + FastAPI
* **Intelligence Layer**: OpenAI API + Pydantic
* **Optimization Layer**: Google OR-Tools CP-SAT
* **Database**: SQLite

## Folder Structure

```text
constraint-canvas-ai/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   └── main.py
│   ├── data/
│   │   └── .gitkeep
│   ├── .env.example
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── api.js
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── .env.example
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
│
├── .gitignore
└── README.md
```

## Setup and Running Instructions (Phase 1)

### 1. Environment Configuration

Copy the example environment files:

```bash
# Backend environment
cp backend/.env.example backend/.env

# Frontend environment
cp frontend/.env.example frontend/.env
```

### 2. Backend Setup & Startup

Ensure Python 3.10+ is installed.

```bash
# Navigate to backend directory
cd backend

# Create virtual environment (optional but recommended)
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI server on port 8000
uvicorn app.main:app --reload --port 8000
```

The backend server runs at `http://localhost:8000`.

### 3. Frontend Setup & Startup

```bash
# Navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Run Vite dev server on port 5173
npm run dev
```

The frontend application will be available at `http://localhost:5173`.

## API Documentation (Phase 1)

### GET `/api/health`

Checks system status and availability.

**Response:**
```json
{
  "status": "healthy",
  "openai_configured": false,
  "database": "connected",
  "optimizer": "available"
}
```
