# Momentum

An AI productivity coach that turns a goal into a concrete task list, tracks
your tasks and notes, and chats with you about what to work on next —
calibrated to how you actually work.

## The problem it solves

Most task managers make you do the hard part yourself: turning a vague goal
("get fit", "ship the v1") into a concrete, doable plan. Momentum asks about
your working style and mindset once, then uses that context every time it
breaks a goal into atomic tasks or chats with you as a coach — so the
suggestions are calibrated to you instead of generic advice.

## Tech stack

- **Frontend**: React, Tailwind CSS, shadcn/ui, react-router, react-query
- **Backend**: FastAPI (Python 3.11), Motor (async MongoDB driver)
- **Database**: MongoDB
- **Auth**: JWT in an httpOnly cookie, bcrypt password hashing
- **AI**: `emergentintegrations` LLM client (Anthropic Claude) for goal
  breakdown (structured JSON) and a streaming (SSE) coach chat
- **Testing**: pytest (backend), CRA/craco test runner (frontend)

## How to run it locally

Requires Python 3.11+, Node.js, and a MongoDB instance (local or hosted).

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env   # fill in MONGO_URL, DB_NAME, JWT_SECRET,
                           # EMERGENT_LLM_KEY, FRONTEND_URL
uvicorn server:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
yarn install   # or npm install
cp ../.env.example .env   # fill in REACT_APP_BACKEND_URL (e.g. http://localhost:8000)
yarn start     # or npm start — http://localhost:3000
```

Run backend tests with `pytest` from `backend/` (requires `REACT_APP_BACKEND_URL`
pointed at a running backend).

## Architecture

```
frontend/   React SPA (pages: Landing, Login/Register, Dashboard, Tasks,
            Goals, Notes, Chat, Profile) — talks to the backend only via
            REACT_APP_BACKEND_URL, all requests under /api
backend/    FastAPI app (server.py) — auth, tasks, goals, notes, dashboard
            stats, and two AI endpoints:
              POST /api/ai/breakdown-goal   goal -> 5-8 tasks (JSON)
              GET  /api/chat/stream         coach chat (SSE)
            reads/writes MongoDB via Motor; JWT auth via httpOnly cookie
MongoDB     stores users, tasks, goals, notes, chat_messages
```

The frontend never talks to the LLM or MongoDB directly — everything goes
through the FastAPI backend, which is the only service holding the database
connection and the LLM key. The AI endpoints build their prompts from the
user's stored profile (working style, mindset, preferences) plus their
current tasks/goals, so every AI response is grounded in that user's own
data.

## Screenshots

<!-- TODO: add screenshots of the dashboard, goal breakdown, and coach chat -->
