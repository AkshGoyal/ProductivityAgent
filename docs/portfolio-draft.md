# Portfolio draft — ProductivityAgent (Momentum)

Draft material for review. Everything below is derived from the repo's code,
commit history, README, and config, plus the repo owner's answers (noted
inline) to the questions raised in the previous draft — anything else I
couldn't verify is marked **[INFERRED]**.

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

**How it was built (per the repo owner):** Aksh wrote the product spec and
prompt, directed the build on the Emergent AI app-building platform, then
reviewed and iterated on the result himself. This wasn't written
commit-by-commit by hand — see the note at the top of "Hard parts and
decisions" for what that means for how this section was researched.

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
authored by `emergent-agent-e1`, with no descriptive messages. So the items
below come from reading the current code directly, not from commit
messages. Per the repo owner, the implementation itself (including the
specific choices below) came from directing the Emergent platform against
his own spec, followed by his own review and iteration — not from
hand-writing each commit.

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
  every `user_id`-scoped query from multi-user mode. Confirmed by the repo
  owner: this single-user auto-login is the mode actually used day to day;
  the multi-user register/login flow exists in the code but isn't the
  active path.
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

_TODO — to be filled in._ Confirmed so far: the repo owner uses Momentum
himself, day to day. On the "100% tested" claim in `test_result.md` /
`test_reports/iteration_*.json` — per the repo owner, that's not the
platform's self-reported figure being taken at face value; he verified it
himself by testing the app directly.

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

## 3. Questions for Aksh — resolved

The previous draft's four questions are now answered and incorporated above
(authorship/framing in "What I built" and the Hard parts note, auth mode in
Hard parts, the testing claim and daily use in Outcome). Recorded here for
traceability:

1. Role: wrote the product spec/prompt, directed the build on Emergent,
   then reviewed and iterated on it himself.
2. Auth mode in active use: single-user auto-login.
3. The "100%" testing claim: not taken from the platform's self-report —
   verified directly by the owner's own testing.
4. Daily use: yes, uses Momentum himself day to day.
