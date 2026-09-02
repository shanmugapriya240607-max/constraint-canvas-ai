# ConstraintCanvas AI - Project Specification

Build a complete, working full-stack prototype named **ConstraintCanvas AI**. Create all files directly in the workspace. The application must run reliably during normal use without blank screens, uncaught exceptions or fake results.

Do not stop after creating the UI. Do not provide only code snippets or instructions. Build, run and verify the complete application.

# REQUIRED TECHNOLOGY STACK

Use exactly:

* Frontend: React + Vite using plain JavaScript
* Backend: Python + FastAPI
* Intelligence layer: ChatGPT through the OpenAI API + Pydantic
* Optimization layer: Google OR-Tools CP-SAT
* Database: SQLite
* Visualization: Gantt chart + Table + Timeline

Do not use:

* TypeScript
* Next.js
* Node.js backend
* Express
* MySQL
* PostgreSQL
* MongoDB
* Firebase
* Supabase
* PuLP
* Hard-coded task data
* Fake optimization results

# REQUIRED PROJECT STRUCTURE

Create:

```text
constraint-canvas-ai/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── schemas.py
│   │   ├── ai_parser.py
│   │   ├── validator.py
│   │   ├── priority_engine.py
│   │   ├── solver.py
│   │   └── database.py
│   ├── data/
│   │   └── .gitkeep
│   ├── tests/
│   │   ├── test_validator.py
│   │   └── test_solver.py
│   ├── .env.example
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ProblemInput.jsx
│   │   │   ├── ExtractedData.jsx
│   │   │   ├── ResultTable.jsx
│   │   │   ├── GanttChart.jsx
│   │   │   ├── TaskTimeline.jsx
│   │   │   ├── LoadingState.jsx
│   │   │   └── ErrorMessage.jsx
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

# APPLICATION WORKFLOW

Implement this exact workflow:

```text
User enters planning requirement
        ↓
React sends text to FastAPI
        ↓
FastAPI sends text to ChatGPT
        ↓
ChatGPT extracts structured JSON
        ↓
Pydantic validates the JSON
        ↓
Python validates dependencies and constraints
        ↓
Priority engine calculates execution priority
        ↓
Google OR-Tools creates the schedule
        ↓
Result is stored in SQLite
        ↓
React displays Table + Gantt + Timeline
```

# BACKEND

Create a Python FastAPI application.

Run it using:

```bash
uvicorn app.main:app --reload --port 8000
```

Enable CORS only for:

```text
http://localhost:5173
```

## Environment variables

Read these variables from `backend/.env`:

```env
OPENAI_API_KEY=
OPENAI_MODEL=
DATABASE_URL=sqlite:///./data/constraint_canvas.db
FRONTEND_ORIGIN=http://localhost:5173
```

Create `backend/.env.example` containing the same variable names with no secret values.

Never expose `OPENAI_API_KEY` through:

* React code
* API responses
* Console output
* Error messages
* Git
* README
* Screenshots

# PYDANTIC SCHEMA

Use Pydantic to validate the exact structured output returned by ChatGPT.

Create these models:

* PlanningRequest
* ExtractedProblem
* Task
* Objective
* MissingInformation
* ValidationError
* ScheduledTask
* SolveResponse

The extracted ChatGPT data must follow:

```json
{
  "problem_title": "Morning office schedule",
  "objective": {
    "type": "LATEST_START",
    "description": "Start the morning routine as late as possible while reaching the office by 09:00"
  },
  "tasks": [
    {
      "id": "task_1",
      "name": "Wake up",
      "duration_minutes": 5,
      "earliest_start": null,
      "deadline": null,
      "depends_on": [],
      "resources": ["person"],
      "is_passive": false,
      "source_text": "Waking up takes 5 minutes"
    },
    {
      "id": "task_2",
      "name": "Get ready",
      "duration_minutes": 30,
      "earliest_start": null,
      "deadline": null,
      "depends_on": ["task_1"],
      "resources": ["person"],
      "is_passive": false,
      "source_text": "Getting ready takes 30 minutes"
    }
  ],
  "missing_information": [],
  "ambiguities": [],
  "assumptions": [],
  "extraction_confidence": 0.95
}
```

## Allowed objective types

Support:

```text
MINIMIZE_MAKESPAN
EARLIEST_FINISH
LATEST_START
```

If the user does not provide an objective and a safe default cannot be determined, return a missing-information question instead of inventing an objective.

## Task validation rules

* `id` must be unique.
* `name` cannot be empty.
* `duration_minutes` must be a positive integer or null.
* `earliest_start` must use 24-hour `HH:MM` format or null.
* `deadline` must use 24-hour `HH:MM` format or null.
* `depends_on` must contain valid task IDs.
* `resources` must be a list of strings.
* `is_passive` must be true or false.
* `extraction_confidence` must be between 0 and 1.
* Unknown durations must remain null.
* ChatGPT must not invent missing durations.

# CHATGPT INTEGRATION

Use the official OpenAI Python SDK.

Use the OpenAI Responses API with Structured Outputs and the Pydantic schema.

The model must come from:

```env
OPENAI_MODEL=
```

The API key must come from:

```env
OPENAI_API_KEY=
```

Do not use Markdown code fences in the model response.

Do not parse arbitrary prose using fragile substring operations if Structured Outputs can return validated data directly.

Use this extraction instruction:

```text
You are a planning-task extraction engine.

Read the user's planning requirement and convert it into structured planning data.

Identify:
1. Problem title
2. Optimization objective
3. Tasks
4. Duration of every task
5. Earliest start times
6. Deadlines
7. Task dependencies
8. Required resources
9. Passive tasks
10. Missing information
11. Ambiguities
12. Assumptions

Rules:
- Return data conforming exactly to the supplied schema.
- Never invent a duration, deadline or start time.
- If a duration is not stated, use null and add a missing-information question.
- A dependency must represent a real before/after requirement.
- Words such as “before,” “after,” “only then” and “must finish before” indicate dependencies.
- Sentence order alone does not prove a dependency.
- Preserve the original source text for each task.
- Use 24-hour HH:MM time.
- Mark automatic background activities such as a washing-machine cycle as passive only when the text supports it.
- Do not calculate the final schedule.
- Do not return Markdown.
```

# MISSING INFORMATION

The application must work generically without hard-coding example tasks.

However, optimization is impossible when required numerical information is missing.

If any required task duration or deadline is missing, return:

```json
{
  "status": "NEEDS_INPUT",
  "message": "More information is required before optimization.",
  "questions": [
    "How many minutes does waking up take?"
  ],
  "tasks": []
}
```

Do not send incomplete data to OR-Tools.

The React frontend must display the questions clearly and ask the user to update the original text.

Do not invent values just to make the solver run.

# DETERMINISTIC VALIDATION

After Pydantic validation, validate the extracted data using Python.

Check:

* Empty task list
* Duplicate task IDs
* Empty task names
* Missing durations
* Zero or negative durations
* Invalid time formats
* Dependencies referencing unknown task IDs
* A task depending on itself
* Circular dependencies
* Deadline earlier than earliest start
* Total task time exceeding the available deadline
* Unknown objective type

Detect circular dependencies using a graph algorithm such as Kahn’s algorithm or depth-first search.

If validation fails, return:

```json
{
  "status": "INVALID",
  "message": "The extracted planning model contains invalid constraints.",
  "errors": [
    {
      "code": "CIRCULAR_DEPENDENCY",
      "message": "A circular dependency was detected.",
      "tasks": ["Task A", "Task B"]
    }
  ],
  "tasks": []
}
```

Do not call OR-Tools when deterministic validation fails.

# PRIORITY ENGINE

Calculate execution priority using dependencies.

Hard dependencies must override numerical priority.

For each task, calculate:

* Execution level
* Number of direct and indirect dependent tasks
* Whether it is a root task
* Whether it is a final task
* Whether it is deadline-critical

Use:

```text
Priority Score =
50% downstream dependency impact
+ 30% deadline urgency
+ 20% critical-path importance
```

A task that unlocks several other tasks should receive a higher execution priority.

Do not confuse task importance with execution order.

For example:

* Reaching the office may be the most important outcome.
* Waking up must execute first because later tasks depend on it.

Return for every task:

```json
{
  "execution_level": 1,
  "priority_score": 85,
  "priority_reason": "This task must finish before three dependent tasks can begin."
}
```

# GOOGLE OR-TOOLS CP-SAT

Use Google OR-Tools CP-SAT to generate the schedule.

Convert `HH:MM` values into minutes from midnight.

Use a scheduling horizon of:

```text
0 to 1439 minutes
```

Create for every task:

* Integer start variable
* Integer end variable
* Interval variable
* Fixed duration

Enforce:

## Dependencies

For every dependency:

```text
predecessor end <= successor start
```

## Deadlines

For every deadline:

```text
task end <= deadline in minutes
```

## Earliest start

For every earliest start:

```text
task start >= earliest start in minutes
```

## Resource non-overlap

Tasks requiring the same exclusive resource must not overlap.

For normal personal tasks using the `person` resource, use:

```python
model.AddNoOverlap(person_intervals)
```

Without this constraint, independent personal tasks may incorrectly run at the same time.

Passive tasks must not occupy the person for their entire duration unless the input explicitly requires supervision.

## Objective handling

### MINIMIZE_MAKESPAN

Create a makespan variable equal to the maximum task end time and minimize it.

### EARLIEST_FINISH

Minimize the final completion time.

### LATEST_START

When a final deadline exists, maximize the start time of the root task while still satisfying all dependencies and deadlines.

This prevents a morning schedule from unnecessarily starting at midnight.

# SOLVER STATUS

Return only:

```text
OPTIMAL
FEASIBLE
INFEASIBLE
UNKNOWN
NEEDS_INPUT
INVALID
ERROR
```

Map OR-Tools statuses correctly.

Never report `FEASIBLE` as `OPTIMAL`.

If OR-Tools returns `INFEASIBLE`, return HTTP 200:

```json
{
  "status": "INFEASIBLE",
  "message": "No feasible schedule found — check your constraints.",
  "explanation": "The required tasks cannot be completed before the stated deadline.",
  "tasks": []
}
```

Do not raise an exception for an infeasible planning problem.

# MAIN API

Create:

```http
POST /api/solve
```

Request:

```json
{
  "text": "User planning requirement"
}
```

Successful response:

```json
{
  "status": "OPTIMAL",
  "problem_title": "Morning office schedule",
  "objective": "Start as late as possible",
  "extraction_confidence": 0.95,
  "makespan_minutes": 95,
  "tasks": [
    {
      "id": "task_1",
      "name": "Wake up",
      "start": "07:25",
      "end": "07:30",
      "duration_minutes": 5,
      "depends_on": [],
      "execution_level": 1,
      "priority_score": 85,
      "priority_reason": "This task unlocks the remaining morning tasks.",
      "is_critical": true
    }
  ],
  "explanation": "The routine begins at 07:25 and completes by 09:00."
}
```

Also create:

```http
GET /api/health
GET /api/history
```

Health response:

```json
{
  "status": "healthy",
  "openai_configured": true,
  "database": "connected",
  "optimizer": "available"
}
```

Never return the API key.

# SQLITE DATABASE

Use SQLite with Python’s built-in `sqlite3` library or SQLAlchemy.

Store the database at:

```text
backend/data/constraint_canvas.db
```

Create a table named `solve_runs` containing:

```text
id
original_text
extracted_json
status
result_json
created_at
```

After every completed request, save:

* Original user text
* Extracted structured data
* Solver status
* Final response
* Created timestamp

Do not save the API key.

Do not commit the generated `.db` file.

# BACKEND ERROR HANDLING

Handle these cases:

## Empty input

Missing or empty `text` must return HTTP 400:

```json
{
  "detail": "Planning text is required."
}
```

## OpenAI API key missing

Return a safe configuration error.

Do not crash during startup.

## Invalid OpenAI response

If ChatGPT returns data that cannot pass Pydantic validation, catch the error and return HTTP 502:

```json
{
  "detail": "The intelligence service returned an invalid planning structure. Please try again."
}
```

## OpenAI timeout or connection failure

Return HTTP 502 with a safe message.

## OR-Tools infeasible result

Return HTTP 200 with `INFEASIBLE`.

## Unexpected exception

Log the technical error only on the backend.

Return HTTP 500:

```json
{
  "detail": "An unexpected server error occurred. Please try again."
}
```

Never return:

* Raw stack traces
* Environment values
* API keys
* Internal filesystem paths

# REQUIREMENTS.TXT

Include:

```text
fastapi
uvicorn[standard]
openai
pydantic
ortools
python-dotenv
sqlalchemy
pytest
httpx
```

# REACT FRONTEND

Use React with Vite and plain JavaScript.

Do not use TypeScript.

Run with:

```bash
npm run dev
```

The application must open at:

```text
http://localhost:5173
```

## Main interface

Create one responsive page containing:

### Header

Display:

```text
ConstraintCanvas AI
Natural-Language Planning and Optimization
```

Show three status indicators:

* ChatGPT
* Validation
* OR-Tools

### Problem input

Include:

* Large textarea
* Analyze button
* Clear button
* Load Office Example button
* Character counter

Disable Analyze when input is empty.

### Loading state

When Analyze is clicked:

* Disable the button
* Show a spinner
* Display:

```text
Understanding requirements → Validating tasks → Optimizing schedule
```

Prevent duplicate submissions.

### Extracted-data section

After success, display:

* Problem title
* Objective
* Extraction confidence
* Number of tasks
* Number of dependencies
* Solver status

### Result table

Columns:

```text
Priority
Task
Duration
Start
End
Dependencies
Reason
```

### Gantt chart

Build a simple responsive Gantt chart using React and CSS.

Display:

* Time scale
* Task name
* Start position
* Duration width
* Critical tasks in amber
* Normal tasks in violet
* Passive tasks in cyan
* Tooltips showing task details

Do not use fake static bars.

Calculate bar positions from the actual start and end times returned by FastAPI.

### Timeline

Display the scheduled tasks in execution order.

Each timeline card must show:

* Task name
* Start and end time
* Execution level
* Priority reason
* Critical-path status

## Status handling

### OPTIMAL or FEASIBLE

Show table, Gantt chart and timeline.

### NEEDS_INPUT

Show:

```text
More information is required.
```

List every clarification question.

Do not show an empty schedule table.

### INVALID

Show all validation errors.

### INFEASIBLE

Show:

```text
No feasible schedule found — check your constraints.
```

Display the explanation.

### Network or server error

Show a visible error message.

Never leave a blank page.

# FRONTEND API

Create:

```text
frontend/src/api.js
```

Use:

```text
VITE_API_BASE_URL=http://localhost:8000
```

Call:

```http
POST /api/solve
```

with:

```json
{
  "text": "..."
}
```

Use `try`, `catch` and `finally`.

Always stop the loading state in `finally`.

# BASIC VISUAL DESIGN

Use a clean professional interface.

Colours:

```text
Background: #07101D
Panel: #0D1827
Input: #081522
Border: #21334A
Primary violet: #8B75FF
Cyan: #32D9DF
Success: #66D2A8
Warning: #FFBE5C
Error: #FF667F
Primary text: #EDF3FF
Secondary text: #8EA0B9
```

Requirements:

* Responsive desktop and mobile layout
* Readable typography
* Minimum 44px button height
* No horizontal page overflow
* Clear focus states
* No broken layout when errors are long
* Accessible labels
* Proper table scrolling on mobile

# OFFICE VERIFICATION EXAMPLE

Use this complete example for testing:

```text
Tomorrow I must reach the office by 9:00 AM. I want to start my morning routine as late as possible. Waking up takes 5 minutes. After waking up, I need to get ready for 30 minutes. After getting ready, I need to eat breakfast for 20 minutes. After breakfast, I need to travel to the office for 40 minutes. Travel must finish by 9:00 AM. These tasks must happen in that order.
```

Expected total duration:

```text
95 minutes
```

A correct latest-start schedule should be:

```text
Wake up: 07:25–07:30
Get ready: 07:30–08:00
Eat breakfast: 08:00–08:20
Travel to office: 08:20–09:00
```

Do not hard-code this result.

The result must be generated from ChatGPT extraction and OR-Tools constraints.

# SECOND GENERIC VERIFICATION EXAMPLE

Create and test a completely different planning problem.

For example:

```text
I can start studying at 6:00 PM. Mathematics takes 45 minutes. After Mathematics, Physics takes 30 minutes. Reading takes 20 minutes and can be completed independently. Finish everything as early as possible.
```

The application must extract and solve it without using hard-coded task names or numbers.

# MISSING-DATA VERIFICATION

Test:

```text
I need to wake up, get ready and go to the office.
```

Expected behaviour:

```text
NEEDS_INPUT
```

It must ask for missing durations and deadline/objective information.

It must not invent values.

# EMPTY-INPUT VERIFICATION

Submit an empty textarea.

Expected behaviour:

* Frontend blocks the request or backend returns HTTP 400.
* A clear error message appears.
* No crash occurs.

# INFEASIBLE VERIFICATION

Test a problem where the tasks cannot fit before the deadline.

Expected behaviour:

```text
INFEASIBLE
```

The frontend must show the infeasible message and not display a broken table.

# AUTOMATED TESTS

Create backend tests for:

* Time conversion
* Valid dependency chain
* Unknown dependency
* Self-dependency
* Circular dependency
* Missing duration
* Correct latest-start schedule
* Correct earliest-finish schedule
* Infeasible deadline
* Empty request validation

Run:

```bash
pytest
```

All tests must pass.

# GIT AND GITHUB

Initialize Git if the project is not already inside a repository.

Create these meaningful commits only after each stage works:

```text
chore: initialize React and FastAPI project
feat: integrate ChatGPT task extraction
feat: add Pydantic planning validation
feat: implement OR-Tools scheduling
feat: add SQLite solve history
feat: add table Gantt and timeline results
test: verify generic planning workflows
docs: add complete setup and demo guide
```

Before every commit:

```bash
git status
```

Do not commit:

* `.env`
* API keys
* `node_modules`
* Python virtual environment
* SQLite `.db` file
* Python cache
* Frontend build files

If a GitHub remote named `origin` is already configured and authentication is available, push after each successful commit.

Do not invent a GitHub URL or expose credentials.

# README

Create a complete README containing:

* Project overview
* Architecture
* Technology stack
* Folder structure
* Environment setup
* Backend installation
* Frontend installation
* Running instructions
* API documentation
* Testing instructions
* Example inputs
* Expected office-example output
* Error-handling behaviour
* Current limitations
* Future improvements

Include:

```text
ChatGPT extracts structured tasks and dependencies from natural language. Pydantic validates the extracted structure. Deterministic Python rules verify dependency correctness. Google OR-Tools performs scheduling optimization. SQLite stores solve history. React presents the result through a table, Gantt chart and timeline.
```

# FINAL VERIFICATION

Before reporting completion:

1. Install all backend dependencies.
2. Install all frontend dependencies.
3. Start FastAPI on port 8000.
4. Start React on port 5173.
5. Verify `GET /api/health`.
6. Test the complete office example.
7. Confirm the office schedule finishes at 09:00.
8. Test a completely different planning problem.
9. Test missing-duration input.
10. Test empty input.
11. Test an infeasible deadline.
12. Refresh the frontend.
13. Repeat the office test.
14. Confirm SQLite contains the saved runs.
15. Confirm the table uses actual API data.
16. Confirm the Gantt chart uses actual API data.
17. Confirm the timeline uses actual API data.
18. Confirm there are no browser-console errors.
19. Confirm there are no backend-terminal errors.
20. Run `pytest`.
21. Run `npm run build`.
22. Fix every reported error.

Only say the project is complete after all verification steps pass.

Show the actual outputs of:

```text
GET /api/health
Office-example solve
Second generic-example solve
Missing-data test
Infeasible test
pytest
npm run build
git log --oneline
```

Do not stop until the application runs correctly end to end.
