# Plan My Day

A personal productivity coach: you give it a goal, it breaks the goal into
tasks small enough to actually start, and it tells you which of them to do
today — calibrated to how you work rather than to generic advice.

Single-user tool that runs on your own machine. Your tasks, goals and notes
stay in a SQLite file you own.

## What it does

- **Goal breakdown** — turn "launch the newsletter" into 5–8 concrete tasks,
  each sized for one focused sitting.
- **Plan my day** — pick and order today's work from everything that's open,
  against the time you actually have.
- **Coach chat** — talk through what's stuck, grounded in your real tasks,
  goals and notes rather than invented context.
- **Profile** — describe your working style and mindset once; every prompt is
  built from it.
- **Notes** — think out loud; recent notes feed the coach's context.

## Stack

Python 3.11 · FastAPI · SQLite (stdlib `sqlite3`) · Google Gemini via
`google-genai` · one static HTML page, no build step.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # add your GEMINI_API_KEY
export $(grep -v '^#' .env | xargs)

python -m app.main            # http://127.0.0.1:8000
```

Run the tests with `pytest`. The LLM client is mocked throughout, so the suite
needs no API key and makes no live calls.

## How it's built

```
app/config.py    every setting in one place — model, paths, context limits
app/db.py        SQLite schema and connection; re-runnable migrations
app/models.py    Pydantic models: HTTP contracts and LLM output schemas
app/llm.py       the single wrapper every Gemini call goes through
app/context.py   database rows -> the bounded text blocks prompts interpolate
app/prompts/     prompt templates as files, not f-strings in the routes
app/repo.py      every SQL statement in the project
app/api.py       routes, all under /api
static/          one page, vanilla JS
```

Deterministic code does the work; the model is called only where judgment is
needed — breaking a goal down, ordering a day, coaching. Three design rules
hold that together:

**Structured output, never string-parsing.** Each LLM call passes a Pydantic
model as Gemini's `response_schema` and gets a validated instance back.
Enumerated fields are `Literal[...]`, so the model cannot return a priority or
status the database would reject. Nothing parses model output with a regex.

**Verify against the database, don't trust the model.** `plan-day` asks for
task ids and then checks every one against real rows, dropping anything it
doesn't recognise — a hallucinated id can't reach the UI. There's a test for
exactly that.

**Bounded context.** Prompts are built from capped queries, so prompt size
stays predictable as the database grows.

### On retries

`google-genai` makes exactly one attempt per call and raises immediately on a
429 or a transient 503, unlike some other SDKs. `llm.get_client()` sets
`HttpRetryOptions` explicitly so overload becomes a retry rather than a failed
request, and a test asserts the option is set so it can't regress quietly.

### Security note

There is no auth layer — this is a single-user local tool, and it binds to
`127.0.0.1` for that reason. Don't expose it on a public interface without
adding authentication first.

## History

This started life on a hosted AI app-building platform as a React + MongoDB
app. It was rebuilt here on FastAPI + SQLite + Gemini: a stack I run myself,
with schema-enforced model output, real retry behaviour, and a test suite in
place of the generated version's regex parsing and unguarded calls. The
original implementation is in this repository's git history.
