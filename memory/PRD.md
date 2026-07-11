# Momentum — Productivity Agent (PRD)

## Original Problem Statement
> I want to build a productivity agent, which helps manage my tasks, calibrate the tasks, give it goals and it breaks down, give it my style of working, give it my mindset, it has a notes section also which I can just use to express my thoughts along the way, any other features that would require in a complete solution for productivity management.

## Architecture
- **Frontend**: React + Tailwind + shadcn/ui, routes via react-router. Cabinet Grotesk (headings) + Manrope (body). Earthy Swiss palette.
- **Backend**: FastAPI (Python 3.11) + Motor (MongoDB). All routes under `/api`.
- **Auth**: JWT (7-day) in httpOnly cookie `access_token`, with `Authorization: Bearer` fallback. bcrypt password hashing.
- **AI**: `emergentintegrations.llm.chat.LlmChat` with `anthropic/claude-sonnet-4-6` via Emergent Universal LLM Key.
  - Goal breakdown: non-streaming (collected) JSON parsing → task inserts.
  - Coach chat: SSE (`text/event-stream`) with `X-Accel-Buffering: no`.

## User Personas
- **Solo builder / IC**: wants to translate ambition into concrete atomic tasks calibrated to their personal working style.
- **Reflective operator**: uses notes + coach chat to think through blockers.

## Core Requirements (implemented — 2026-02-11)
- Email/password auth (register, login, logout, me, profile update).
- Profile: name, working_style, mindset, preferences → injected into every AI prompt.
- Tasks: title, description, priority (low/med/high), status (todo/in_progress/done), due date, optional goal link.
- Goals: title, description, target_date, status, computed progress (`done/total`).
- **AI goal breakdown**: POST `/api/ai/breakdown-goal` → generates 5-8 atomic tasks tailored to profile.
- **AI coach chat**: streaming SSE at `/api/chat/stream`; system prompt includes profile + open tasks + active goals + last 30 messages. History persisted in `chat_messages`.
- Notes / Journal: title + free-form content, sidebar list + editor pane.
- Dashboard: open-task count, completion rate, active goals, notes count, "what's next" list, goal progress.
- Landing page, protected routes, sonner toasts, data-testids on all interactive elements.

## Prioritized Backlog
- **P1**: Pomodoro / focus timer, calendar view (react-day-picker + goal target dates), daily plan generation ("plan my day"), recurring tasks.
- **P2**: Analytics charts (streaks, priority mix), tags on notes, note→task extraction via AI, task reminders (email via Resend), mobile-optimized bottom nav.
- **P3**: Shareable public goal timelines, team/collab, integrations (Google Calendar, GitHub issues).

## Testing
- Iteration 1 (2026-02-11): 100% backend + 100% frontend. Auth, tasks, goals, notes, AI breakdown, chat streaming, profile all verified end-to-end.
- Test creds: `demo@momentum.app` / `password123`.

## Environment
- Backend `.env`: `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `EMERGENT_LLM_KEY`, `FRONTEND_URL`.
- Frontend `.env`: `REACT_APP_BACKEND_URL`.
