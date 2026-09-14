# Portfolio draft — ProductivityAgent (Momentum)

Draft material for review. Everything below is derived from the repo's code,
commit history, README, and config — anything I couldn't verify from those
sources is marked **[INFERRED]**, and open questions are listed at the end.
**Read the first question below before using this draft** — it affects how
the whole case study should be framed.

---

## 1. GitHub repo description & topics

**Description** (97 chars):
> AI productivity coach that breaks goals into tasks and coaches you via a tool-calling chat agent.

**Topics:**
`react` `fastapi` `mongodb` `llm` `claude-api` `productivity` `tailwindcss` `jwt-auth`

---

## 2. Case study

### Problem

Generic task managers require you to do the hard part yourself: turning a
vague goal into a concrete, doable plan. `memory/PRD.md` records the
original problem statement this app was built from: "a productivity agent,
which helps manage my tasks, calibrate the tasks, give it goals and it
breaks them down, give it my style of working, give it my mindset... any
other features that would require in a complete solution for productivity
management." The product is for one person managing their own tasks, goals,
and notes, calibrated to how they personally work.

### What I built

**In plain terms:** A web app ("Momentum") where you set goals, and an AI
coach breaks each one into 5–8 concrete tasks sized to be done in a single
sitting, tailored to a working-style/mindset profile you set once. You can
chat with the coach in a live, streaming conversation about what to work on.
There's also a second, more autonomous chat mode — a persistent "agent" —
that can directly create tasks, update task status, break down goals, and
add notes on your behalf mid-conversation, rather than just suggesting them.

**Architecture:**
```
frontend/   React SPA (Dashboard, Tasks, Goals, Notes, Chat, Profile pages)
            — talks to the backend only via REACT_APP_BACKEND_URL, all requests under /api
backend/    FastAPI app (server.py) — auth, tasks, goals, notes, dashboard stats,
            and three AI-backed endpoints:
              POST /api/ai/breakdown-goal   goal -> 5-8 tasks (one-shot JSON)
              GET  /api/chat/stream         coach chat (SSE)
              POST /api/agent/chat          tool-calling agent (JSON reply + actions)
            reads/writes MongoDB via Motor; JWT auth via httpOnly cookie
MongoDB     users, tasks, goals, notes, chat_messages, agent_messages
Claude      claude-sonnet-4-6, called via the `emergentintegrations` LLM client
```
The frontend never talks to MongoDB or the LLM directly — every request
goes through the FastAPI backend, which is the only service holding the
database connection and the LLM key.

### Hard parts and decisions

**A note on how this section was researched:** the commit history isn't
useful for finding these the normal way — every commit before this
portfolio-prep PR is `auto-commit for <uuid>` or `Auto-generated changes`,
authored by `emergent-agent-e1`, with no descriptive messages. So the
items below come from reading the current code directly, not from commit
messages. See question 1 below — this also means I can't confirm from the
repo alone which of these decisions were made by you versus generated.

- **Whitelisted server-side execution of free-text LLM output.**
  `/api/agent/chat` asks the model to return strict JSON (`{"reply": ...,
  "actions": [...]}`), extracts it with a regex that tolerates stray prose
  or code fences, then — before touching the database — re-validates every
  field of every requested tool call against an explicit whitelist: e.g.
  `priority` must be `low`/`medium`/`high` or it's coerced to `medium`,
  `status` updates are rejected outright if not one of
  `todo`/`in_progress`/`done`, and an `update_task` or `break_down_goal`
  call is rejected unless the referenced `task_id`/`goal_id` already exists
  for that user. This is a manual, per-field version of the validation
  FastAPI/Pydantic provide automatically on the app's regular REST routes.
- **Two coexisting auth modes.** There's a standard bcrypt + JWT
  email/password flow (`/auth/register`, `/auth/login`), and separately a
  `GET /auth/session` endpoint that silently creates-or-reuses one fixed
  `owner@momentum.app` account (given an unusable random password hash) and
  logs the caller in as that user — a single-user bypass that still reuses
  every `user_id`-scoped query from multi-user mode. Flagged as a question
  below since it's not obvious from the code alone which mode the app
  actually runs in day to day.
- **Per-turn context assembly with explicit bounding.** Both the streaming
  coach and the tool-calling agent rebuild their system prompt from the
  user's *live* tasks/goals/notes on every single turn (not just chat
  history), and explicitly truncate the serialized text — e.g.
  `history_str[-4000:]`, goal JSON `[:4000]` — to keep the prompt bounded
  as a user's data grows, rather than relying on the model's own context
  management.
- **No schema on the LLM's JSON output.** Both `/api/ai/breakdown-goal` and
  `/api/agent/chat` parse the model's reply with a permissive regex
  (`\{[\s\S]*\}`) followed by a bare `json.loads` in a `try/except`, falling
  back to treating the raw text as the reply if parsing fails. This is
  workably resilient to a malformed reply, but it also means a response
  containing two JSON-looking blocks, or valid JSON in an unexpected shape,
  degrades silently instead of failing loudly — there's no structured-output
  contract enforcing the shape the way there is for the app's own database
  documents.
- **No retry/backoff around LLM calls.** A failed `stream_message` call
  raises straight into a `500`, and the raised exception's string is
  included directly in the HTTP error detail (e.g. `f"AI error: {e}"`),
  which can surface library-internal error text to the frontend.

### Outcome

_TODO — to be filled in._

### What I'd do next

From `memory/PRD.md`'s own prioritized backlog:
- **P1:** a Pomodoro/focus timer, a calendar view, "plan my day" generation,
  recurring tasks.
- **P2:** analytics (streaks, priority mix), tags on notes, note→task
  extraction via AI, email task reminders (Resend), a mobile-optimized nav.
- **P3:** shareable public goal timelines, team/collaboration features,
  Google Calendar and GitHub integrations.

Separately, from reading the code rather than the backlog: replacing the
regex-plus-`json.loads` parsing on `/api/ai/breakdown-goal` and
`/api/agent/chat` with an enforced structured-output schema, and adding
retry/backoff around the `emergentintegrations` LLM calls, which currently
have none.

---

## 3. Questions for Aksh

1. **This one matters most.** Every commit before this portfolio-prep PR is
   authored `emergent-agent-e1` with messages like `auto-commit for
   <uuid>`, and `test_result.md` is a literal protocol file for an
   autonomous "main_agent"/"testing_agent" workflow — this reads as an app
   built on an AI app-building platform (Emergent) from the one-paragraph
   prompt in `memory/PRD.md`, not hand-coded commit by commit. What was your
   actual role — writing/refining that prompt, steering iterations, manual
   debugging, something else? I don't want to represent this to a hiring
   manager as hands-on engineering work if that's not accurate, and the
   repo alone can't tell me which parts (if any) you wrote or edited
   directly.
2. Which auth mode does the app actually run in day to day — the
   single-user `/auth/session` auto-login, or real multi-user
   registration/login? That changes how I'd describe the product.
3. `test_result.md` / `test_reports/iteration_*.json` record "100%
   backend + 100% frontend" tested as of iteration 1 — is that an
   independently verified result, or the platform's own self-reported
   testing-agent output? I don't want to cite it as a verified metric
   either way without checking with you.
4. Do you actually use Momentum yourself day to day? That would shape
   "Outcome" once you fill it in.
