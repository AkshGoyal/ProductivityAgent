from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import uuid
import logging
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal, AsyncGenerator

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr

from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

# -------------------- Setup --------------------
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
JWT_ALG = "HS256"
DEFAULT_USER_EMAIL = "owner@momentum.app"
DEFAULT_USER_NAME = "Owner"

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="Momentum — Productivity Agent")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# -------------------- Utilities --------------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "type": "access",
               "exp": now_utc() + timedelta(days=7)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="access_token", value=token, httponly=True,
        secure=True, samesite="none", max_age=60 * 60 * 24 * 7, path="/"
    )


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# -------------------- Models --------------------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1, max_length=80)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    name: str
    working_style: str = ""
    mindset: str = ""
    preferences: str = ""
    created_at: str


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    working_style: Optional[str] = None
    mindset: Optional[str] = None
    preferences: Optional[str] = None


class TaskIn(BaseModel):
    title: str
    description: str = ""
    priority: Literal["low", "medium", "high"] = "medium"
    status: Literal["todo", "in_progress", "done"] = "todo"
    due_date: Optional[str] = None
    goal_id: Optional[str] = None
    estimated_minutes: Optional[int] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[Literal["low", "medium", "high"]] = None
    status: Optional[Literal["todo", "in_progress", "done"]] = None
    due_date: Optional[str] = None
    goal_id: Optional[str] = None
    estimated_minutes: Optional[int] = None


class GoalIn(BaseModel):
    title: str
    description: str = ""
    target_date: Optional[str] = None


class GoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_date: Optional[str] = None
    status: Optional[Literal["active", "completed", "paused"]] = None


class NoteIn(BaseModel):
    title: str = ""
    content: str
    mood: Optional[str] = None


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    mood: Optional[str] = None
    reflection: Optional[str] = None


class ChatIn(BaseModel):
    message: str
    session_id: Optional[str] = None


class GoalBreakdownIn(BaseModel):
    goal_id: str


class AgentChatIn(BaseModel):
    message: str


class NoteReflectIn(BaseModel):
    note_id: str
    save: bool = False
    reflection: Optional[str] = None  # if provided AND save=True, persist this text without re-calling the LLM


# -------------------- Auth Routes --------------------
@api.post("/auth/register", response_model=UserOut)
async def register(payload: RegisterIn, response: Response):
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = str(uuid.uuid4())
    doc = {
        "id": user_id,
        "email": email,
        "name": payload.name.strip(),
        "password_hash": hash_password(payload.password),
        "working_style": "",
        "mindset": "",
        "preferences": "",
        "created_at": iso(now_utc()),
    }
    await db.users.insert_one(doc)
    token = create_access_token(user_id, email)
    set_auth_cookie(response, token)
    doc.pop("password_hash", None)
    doc.pop("_id", None)
    return doc


@api.post("/auth/login", response_model=UserOut)
async def login(payload: LoginIn, response: Response):
    email = payload.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user["id"], email)
    set_auth_cookie(response, token)
    user.pop("password_hash", None)
    user.pop("_id", None)
    return user


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api.get("/auth/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    return user


@api.get("/auth/session", response_model=UserOut)
async def session(response: Response):
    """Single-user mode: return (creating if needed) the default owner user and set an auth cookie.
    This bypasses login/signup for personal use while keeping all user_id scoping intact."""
    user = await db.users.find_one({"email": DEFAULT_USER_EMAIL})
    if not user:
        user_id = str(uuid.uuid4())
        doc = {
            "id": user_id,
            "email": DEFAULT_USER_EMAIL,
            "name": DEFAULT_USER_NAME,
            "password_hash": hash_password(uuid.uuid4().hex),  # unusable, never used
            "working_style": "",
            "mindset": "",
            "preferences": "",
            "created_at": iso(now_utc()),
        }
        await db.users.insert_one(doc)
        user = doc
    token = create_access_token(user["id"], user["email"])
    set_auth_cookie(response, token)
    user.pop("password_hash", None)
    user.pop("_id", None)
    return user


@api.patch("/auth/profile", response_model=UserOut)
async def update_profile(payload: ProfileUpdate, user: dict = Depends(get_current_user)):
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if update:
        await db.users.update_one({"id": user["id"]}, {"$set": update})
    updated = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0})
    return updated


# -------------------- Tasks --------------------
@api.get("/tasks")
async def list_tasks(user: dict = Depends(get_current_user),
                     status: Optional[str] = None,
                     goal_id: Optional[str] = None):
    q = {"user_id": user["id"]}
    if status:
        q["status"] = status
    if goal_id:
        q["goal_id"] = goal_id
    tasks = await db.tasks.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return tasks


@api.post("/tasks")
async def create_task(payload: TaskIn, user: dict = Depends(get_current_user)):
    doc = payload.model_dump()
    doc.update({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "created_at": iso(now_utc()),
        "updated_at": iso(now_utc()),
    })
    await db.tasks.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.patch("/tasks/{task_id}")
async def update_task(task_id: str, payload: TaskUpdate, user: dict = Depends(get_current_user)):
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    update["updated_at"] = iso(now_utc())
    result = await db.tasks.update_one({"id": task_id, "user_id": user["id"]}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    task = await db.tasks.find_one({"id": task_id}, {"_id": 0})
    return task


@api.delete("/tasks/{task_id}")
async def delete_task(task_id: str, user: dict = Depends(get_current_user)):
    result = await db.tasks.delete_one({"id": task_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True}


# -------------------- Goals --------------------
@api.get("/goals")
async def list_goals(user: dict = Depends(get_current_user)):
    goals = await db.goals.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    for g in goals:
        cnt = await db.tasks.count_documents({"goal_id": g["id"], "user_id": user["id"]})
        done = await db.tasks.count_documents({"goal_id": g["id"], "user_id": user["id"], "status": "done"})
        g["task_count"] = cnt
        g["done_count"] = done
        g["progress"] = round((done / cnt) * 100) if cnt else 0
    return goals


@api.post("/goals")
async def create_goal(payload: GoalIn, user: dict = Depends(get_current_user)):
    doc = payload.model_dump()
    doc.update({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "status": "active",
        "created_at": iso(now_utc()),
        "updated_at": iso(now_utc()),
    })
    await db.goals.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.patch("/goals/{goal_id}")
async def update_goal(goal_id: str, payload: GoalUpdate, user: dict = Depends(get_current_user)):
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    update["updated_at"] = iso(now_utc())
    result = await db.goals.update_one({"id": goal_id, "user_id": user["id"]}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Goal not found")
    goal = await db.goals.find_one({"id": goal_id}, {"_id": 0})
    return goal


@api.delete("/goals/{goal_id}")
async def delete_goal(goal_id: str, user: dict = Depends(get_current_user)):
    result = await db.goals.delete_one({"id": goal_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Goal not found")
    # unlink tasks
    await db.tasks.update_many({"goal_id": goal_id, "user_id": user["id"]}, {"$set": {"goal_id": None}})
    return {"ok": True}


# -------------------- Notes / Journal --------------------
@api.get("/notes")
async def list_notes(user: dict = Depends(get_current_user)):
    notes = await db.notes.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return notes


@api.post("/notes")
async def create_note(payload: NoteIn, user: dict = Depends(get_current_user)):
    doc = payload.model_dump()
    doc.update({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "created_at": iso(now_utc()),
        "updated_at": iso(now_utc()),
    })
    await db.notes.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.patch("/notes/{note_id}")
async def update_note(note_id: str, payload: NoteUpdate, user: dict = Depends(get_current_user)):
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    update["updated_at"] = iso(now_utc())
    result = await db.notes.update_one({"id": note_id, "user_id": user["id"]}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    note = await db.notes.find_one({"id": note_id}, {"_id": 0})
    return note


@api.delete("/notes/{note_id}")
async def delete_note(note_id: str, user: dict = Depends(get_current_user)):
    result = await db.notes.delete_one({"id": note_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True}


# -------------------- Dashboard --------------------
@api.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    uid = user["id"]
    total_tasks = await db.tasks.count_documents({"user_id": uid})
    done_tasks = await db.tasks.count_documents({"user_id": uid, "status": "done"})
    in_progress = await db.tasks.count_documents({"user_id": uid, "status": "in_progress"})
    goals_active = await db.goals.count_documents({"user_id": uid, "status": "active"})
    goals_done = await db.goals.count_documents({"user_id": uid, "status": "completed"})
    notes_count = await db.notes.count_documents({"user_id": uid})
    return {
        "total_tasks": total_tasks,
        "done_tasks": done_tasks,
        "in_progress_tasks": in_progress,
        "todo_tasks": total_tasks - done_tasks - in_progress,
        "active_goals": goals_active,
        "completed_goals": goals_done,
        "notes_count": notes_count,
        "completion_rate": round((done_tasks / total_tasks) * 100) if total_tasks else 0,
    }


# -------------------- AI: Goal Breakdown --------------------
def build_user_context(user: dict) -> str:
    ws = user.get("working_style") or "Not specified"
    ms = user.get("mindset") or "Not specified"
    pr = user.get("preferences") or "Not specified"
    return (
        f"USER PROFILE\n"
        f"Name: {user.get('name','')}\n"
        f"Working style: {ws}\n"
        f"Mindset: {ms}\n"
        f"Preferences: {pr}\n"
    )


@api.post("/ai/breakdown-goal")
async def breakdown_goal(payload: GoalBreakdownIn, user: dict = Depends(get_current_user)):
    goal = await db.goals.find_one({"id": payload.goal_id, "user_id": user["id"]}, {"_id": 0})
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    ctx = build_user_context(user)
    system = (
        "You are Momentum, a pragmatic productivity coach. Given a user's goal and their profile, "
        "break the goal into 5-8 concrete, atomic, actionable tasks tailored to how they work. "
        "Each task must be specific enough to complete in one focused session (30-120 min). "
        "Return STRICT JSON only with this shape (no prose, no markdown fences):\n"
        '{"tasks":[{"title":"...","description":"...","priority":"low|medium|high","estimated_minutes":60}]}'
    )
    prompt = (
        f"{ctx}\n"
        f"GOAL TITLE: {goal['title']}\n"
        f"GOAL DESCRIPTION: {goal.get('description','')}\n"
        f"TARGET DATE: {goal.get('target_date') or 'not set'}\n"
        "Break this goal down now."
    )

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"breakdown-{payload.goal_id}-{uuid.uuid4()}",
        system_message=system,
    ).with_model("anthropic", "claude-sonnet-4-6")

    result_text = ""
    try:
        async for ev in chat.stream_message(UserMessage(text=prompt)):
            if isinstance(ev, TextDelta):
                result_text += ev.content
            elif isinstance(ev, StreamDone):
                break
    except Exception as e:
        logger.exception("LLM breakdown failed")
        raise HTTPException(status_code=500, detail=f"AI error: {e}")

    import json, re
    # Strip potential code fences
    txt = result_text.strip()
    m = re.search(r"\{[\s\S]*\}", txt)
    if not m:
        raise HTTPException(status_code=500, detail="AI response could not be parsed")
    try:
        parsed = json.loads(m.group(0))
        raw_tasks = parsed.get("tasks", [])
    except Exception:
        raise HTTPException(status_code=500, detail="AI JSON parse failure")

    created = []
    for t in raw_tasks:
        doc = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "goal_id": goal["id"],
            "title": str(t.get("title", "Untitled task"))[:200],
            "description": str(t.get("description", "")),
            "priority": t.get("priority") if t.get("priority") in ("low", "medium", "high") else "medium",
            "status": "todo",
            "due_date": None,
            "estimated_minutes": int(t.get("estimated_minutes", 60)) if str(t.get("estimated_minutes", "")).isdigit() or isinstance(t.get("estimated_minutes"), int) else 60,
            "created_at": iso(now_utc()),
            "updated_at": iso(now_utc()),
        }
        await db.tasks.insert_one(doc)
        doc.pop("_id", None)
        created.append(doc)

    return {"tasks": created}


# -------------------- AI: Coach Chat (streaming SSE) --------------------
@api.get("/chat/history")
async def chat_history(user: dict = Depends(get_current_user), limit: int = 100):
    msgs = await db.chat_messages.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", 1).to_list(limit)
    return msgs


@api.post("/chat/stream")
async def chat_stream(payload: ChatIn, user: dict = Depends(get_current_user)):
    session_id = payload.session_id or "default"

    # Save user message
    user_msg = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "session_id": session_id,
        "role": "user",
        "content": payload.message,
        "created_at": iso(now_utc()),
    }
    await db.chat_messages.insert_one(user_msg)

    # Pull recent context — last 20 for continuity in system prompt (LlmChat manages its own too,
    # but we use a fresh chat per request and pass compressed history)
    prior = await db.chat_messages.find(
        {"user_id": user["id"], "session_id": session_id},
        {"_id": 0, "role": 1, "content": 1}
    ).sort("created_at", 1).to_list(30)

    ctx = build_user_context(user)
    # Pull open tasks & active goals for the coach
    open_tasks = await db.tasks.find(
        {"user_id": user["id"], "status": {"$ne": "done"}}, {"_id": 0, "title": 1, "priority": 1, "due_date": 1}
    ).sort("created_at", -1).to_list(15)
    active_goals = await db.goals.find(
        {"user_id": user["id"], "status": "active"}, {"_id": 0, "title": 1}
    ).sort("created_at", -1).to_list(10)

    tasks_str = "\n".join(f"- [{t.get('priority','?')}] {t['title']}" for t in open_tasks) or "None"
    goals_str = "\n".join(f"- {g['title']}" for g in active_goals) or "None"
    history_str = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in prior[:-1])[-4000:]

    system = (
        "You are Momentum — a calm, incisive productivity coach.\n"
        "Adapt to the user's stated working style and mindset. Be concrete, not preachy.\n"
        "Reference the user's real tasks and goals when useful. Ask sharp questions when helpful.\n"
        "Keep answers tight — bullets when listing, prose when reflecting. Never invent data.\n\n"
        f"{ctx}\n"
        f"ACTIVE GOALS:\n{goals_str}\n\n"
        f"OPEN TASKS (sample):\n{tasks_str}\n\n"
        f"RECENT CONVERSATION:\n{history_str}"
    )

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"{user['id']}-{session_id}",
        system_message=system,
    ).with_model("anthropic", "claude-sonnet-4-6")

    async def event_gen() -> AsyncGenerator[str, None]:
        collected = ""
        try:
            async for ev in chat.stream_message(UserMessage(text=payload.message)):
                if isinstance(ev, TextDelta):
                    collected += ev.content
                    # SSE format
                    safe = ev.content.replace("\r", "")
                    for line in safe.split("\n"):
                        yield f"data: {line}\n"
                    yield "\n"
                elif isinstance(ev, StreamDone):
                    break
        except Exception as e:
            logger.exception("chat stream error")
            yield f"event: error\ndata: {str(e)}\n\n"
        # Persist assistant message
        assistant_msg = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "session_id": session_id,
            "role": "assistant",
            "content": collected,
            "created_at": iso(now_utc()),
        }
        await db.chat_messages.insert_one(assistant_msg)
        yield "event: done\ndata: [DONE]\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@api.delete("/chat/history")
async def clear_history(user: dict = Depends(get_current_user)):
    await db.chat_messages.delete_many({"user_id": user["id"]})
    return {"ok": True}


# -------------------- AI Agent (persistent companion with tools) --------------------
AGENT_SYSTEM_PROMPT = """You are Momentum — a persistent productivity companion and brainstorming partner for a single user.
You help them ideate, plan their day, break down goals, weigh decisions, and reflect on their thoughts — always grounded in THEIR actual working style, mindset, tasks, goals, and notes (all supplied to you on every turn).

Voice: warm but direct. Concrete over preachy. Ask sharp questions. Push back when they're avoiding hard things. Never invent data — if you don't see it in the context, say so.

You have TOOLS. When the user asks you to do something in their workspace (create a task, break down a goal, capture a note, update a task's status/priority), you MUST take that action via a tool call — do not just describe it.

RESPONSE FORMAT — return STRICT JSON only, no markdown fences, no prose outside the JSON:
{
  "reply": "<your natural-language response to the user, 1-6 short paragraphs or bullets>",
  "actions": [
    {"tool": "create_task", "args": {"title": "string", "description": "string (optional)", "priority": "low|medium|high", "goal_id": "string (optional)", "estimated_minutes": 60}},
    {"tool": "update_task", "args": {"task_id": "string", "status": "todo|in_progress|done", "priority": "low|medium|high"}},
    {"tool": "break_down_goal", "args": {"goal_id": "string"}},
    {"tool": "add_note", "args": {"title": "string", "content": "string"}}
  ]
}

Rules:
- `actions` is a list; use [] if no action is warranted.
- Only include tool args that you actually want to set. Omit optional args if unsure.
- For `break_down_goal`, the goal MUST already exist in the user's goals list — reference it by id from the context.
- For `update_task`, use task ids from the OPEN TASKS list in the context.
- Never fabricate task_ids or goal_ids.
- Keep replies tight and useful. Bullets when listing options, prose when reflecting."""


async def _load_agent_context(user: dict) -> str:
    uid = user["id"]
    open_tasks = await db.tasks.find(
        {"user_id": uid, "status": {"$ne": "done"}},
        {"_id": 0, "id": 1, "title": 1, "priority": 1, "status": 1, "due_date": 1, "goal_id": 1},
    ).sort("created_at", -1).to_list(30)
    goals = await db.goals.find(
        {"user_id": uid, "status": "active"},
        {"_id": 0, "id": 1, "title": 1, "description": 1, "target_date": 1},
    ).sort("created_at", -1).to_list(20)
    # Attach subtasks to each goal
    for g in goals:
        subs = await db.tasks.find(
            {"user_id": uid, "goal_id": g["id"]},
            {"_id": 0, "id": 1, "title": 1, "status": 1, "priority": 1},
        ).to_list(50)
        g["subtasks"] = subs
    notes = await db.notes.find(
        {"user_id": uid},
        {"_id": 0, "id": 1, "title": 1, "content": 1, "created_at": 1},
    ).sort("created_at", -1).to_list(10)

    import json as _json
    ctx = build_user_context(user) + "\n"
    ctx += "ACTIVE GOALS (with subtasks):\n"
    ctx += _json.dumps(goals, indent=2, default=str)[:4000] + "\n\n"
    ctx += "OPEN TASKS:\n"
    ctx += _json.dumps(open_tasks, indent=2, default=str)[:3000] + "\n\n"
    ctx += "RECENT NOTES (last 10):\n"
    ctx += _json.dumps(notes, indent=2, default=str)[:4000]
    return ctx


async def _agent_history(user: dict, limit: int = 20) -> list:
    msgs = await db.agent_messages.find(
        {"user_id": user["id"]},
        {"_id": 0, "role": 1, "content": 1, "created_at": 1},
    ).sort("created_at", 1).to_list(limit * 2)
    return msgs[-limit:] if len(msgs) > limit else msgs


async def _run_tool(user: dict, tool: str, args: dict) -> dict:
    """Execute a single tool call. Returns a structured result: {tool, status, result?, error?}"""
    try:
        if tool == "create_task":
            title = str(args.get("title", "")).strip()
            if not title:
                return {"tool": tool, "status": "error", "error": "title required"}
            priority = args.get("priority") if args.get("priority") in ("low", "medium", "high") else "medium"
            doc = {
                "id": str(uuid.uuid4()),
                "user_id": user["id"],
                "title": title[:200],
                "description": str(args.get("description", "")),
                "priority": priority,
                "status": "todo",
                "due_date": args.get("due_date"),
                "goal_id": args.get("goal_id"),
                "estimated_minutes": int(args.get("estimated_minutes", 60)) if isinstance(args.get("estimated_minutes"), (int, float)) else 60,
                "created_at": iso(now_utc()),
                "updated_at": iso(now_utc()),
            }
            await db.tasks.insert_one(doc)
            doc.pop("_id", None)
            return {"tool": tool, "status": "ok", "result": doc, "summary": f"Created task: {doc['title']}"}

        if tool == "update_task":
            task_id = args.get("task_id")
            if not task_id:
                return {"tool": tool, "status": "error", "error": "task_id required"}
            patch = {}
            if args.get("status") in ("todo", "in_progress", "done"):
                patch["status"] = args["status"]
            if args.get("priority") in ("low", "medium", "high"):
                patch["priority"] = args["priority"]
            if not patch:
                return {"tool": tool, "status": "error", "error": "no valid fields to update"}
            patch["updated_at"] = iso(now_utc())
            r = await db.tasks.update_one({"id": task_id, "user_id": user["id"]}, {"$set": patch})
            if r.matched_count == 0:
                return {"tool": tool, "status": "error", "error": "task not found"}
            task = await db.tasks.find_one({"id": task_id}, {"_id": 0})
            return {"tool": tool, "status": "ok", "result": task, "summary": f"Updated task: {task['title']} → {patch.get('status', patch.get('priority'))}"}

        if tool == "add_note":
            content = str(args.get("content", "")).strip()
            if not content:
                return {"tool": tool, "status": "error", "error": "content required"}
            doc = {
                "id": str(uuid.uuid4()),
                "user_id": user["id"],
                "title": str(args.get("title", "")).strip() or "From agent",
                "content": content,
                "mood": args.get("mood"),
                "created_at": iso(now_utc()),
                "updated_at": iso(now_utc()),
            }
            await db.notes.insert_one(doc)
            doc.pop("_id", None)
            return {"tool": tool, "status": "ok", "result": doc, "summary": f"Added note: {doc['title']}"}

        if tool == "break_down_goal":
            goal_id = args.get("goal_id")
            if not goal_id:
                return {"tool": tool, "status": "error", "error": "goal_id required"}
            goal = await db.goals.find_one({"id": goal_id, "user_id": user["id"]}, {"_id": 0})
            if not goal:
                return {"tool": tool, "status": "error", "error": "goal not found"}
            # Reuse the existing goal-breakdown logic inline
            ctx = build_user_context(user)
            system = (
                "You are Momentum. Break the goal into 5-8 concrete, atomic tasks tailored to the user's working style. "
                "Return STRICT JSON: {\"tasks\":[{\"title\":\"...\",\"description\":\"...\",\"priority\":\"low|medium|high\",\"estimated_minutes\":60}]}"
            )
            prompt = f"{ctx}\nGOAL: {goal['title']}\nDESCRIPTION: {goal.get('description','')}\nTARGET DATE: {goal.get('target_date') or 'not set'}"
            sub_chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"agent-breakdown-{uuid.uuid4()}",
                system_message=system,
            ).with_model("anthropic", "claude-sonnet-4-6")
            collected = ""
            async for ev in sub_chat.stream_message(UserMessage(text=prompt)):
                if isinstance(ev, TextDelta):
                    collected += ev.content
                elif isinstance(ev, StreamDone):
                    break
            import json as _json, re as _re
            m = _re.search(r"\{[\s\S]*\}", collected)
            if not m:
                return {"tool": tool, "status": "error", "error": "AI response not parseable"}
            parsed = _json.loads(m.group(0))
            created = []
            for t in parsed.get("tasks", []):
                doc = {
                    "id": str(uuid.uuid4()),
                    "user_id": user["id"],
                    "goal_id": goal["id"],
                    "title": str(t.get("title", "Untitled"))[:200],
                    "description": str(t.get("description", "")),
                    "priority": t.get("priority") if t.get("priority") in ("low", "medium", "high") else "medium",
                    "status": "todo",
                    "due_date": None,
                    "estimated_minutes": int(t.get("estimated_minutes", 60)) if isinstance(t.get("estimated_minutes"), (int, float)) else 60,
                    "created_at": iso(now_utc()),
                    "updated_at": iso(now_utc()),
                }
                await db.tasks.insert_one(doc)
                doc.pop("_id", None)
                created.append(doc)
            return {"tool": tool, "status": "ok", "result": {"goal_id": goal_id, "tasks": created}, "summary": f"Broke down '{goal['title']}' into {len(created)} tasks"}

        return {"tool": tool, "status": "error", "error": f"unknown tool: {tool}"}
    except Exception as e:
        logger.exception("tool execution failed")
        return {"tool": tool, "status": "error", "error": str(e)}


async def _call_agent_llm(system: str, history: list, user_message: str) -> str:
    """Send to LLM with compressed history; return full text (agent expects JSON)."""
    convo_str = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)[-6000:]
    combined_system = system + "\n\n---PRIOR CONVERSATION---\n" + convo_str if convo_str else system
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"agent-{uuid.uuid4()}",
        system_message=combined_system,
    ).with_model("anthropic", "claude-sonnet-4-6")
    collected = ""
    async for ev in chat.stream_message(UserMessage(text=user_message)):
        if isinstance(ev, TextDelta):
            collected += ev.content
        elif isinstance(ev, StreamDone):
            break
    return collected


@api.get("/agent/history")
async def agent_history(user: dict = Depends(get_current_user), limit: int = 200):
    msgs = await db.agent_messages.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", 1).to_list(limit)
    return msgs


@api.delete("/agent/history")
async def clear_agent_history(user: dict = Depends(get_current_user)):
    await db.agent_messages.delete_many({"user_id": user["id"]})
    return {"ok": True}


@api.post("/agent/chat")
async def agent_chat(payload: AgentChatIn, user: dict = Depends(get_current_user)):
    text = payload.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="message is required")

    # Persist user turn
    user_msg = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "role": "user",
        "content": text,
        "actions": [],
        "created_at": iso(now_utc()),
    }
    await db.agent_messages.insert_one(user_msg)

    ctx = await _load_agent_context(user)
    history = await _agent_history(user, limit=20)
    system = AGENT_SYSTEM_PROMPT + "\n\n---LIVE CONTEXT (regenerated every turn)---\n" + ctx

    raw = ""
    try:
        raw = await _call_agent_llm(system, history[:-1], text)
    except Exception as e:
        logger.exception("agent llm call failed")
        raise HTTPException(status_code=500, detail=f"Agent LLM error: {e}")

    import json as _json, re as _re
    reply_text = raw.strip()
    actions_to_run = []
    # Extract JSON (tolerate code fences)
    m = _re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            parsed = _json.loads(m.group(0))
            if isinstance(parsed, dict):
                reply_text = str(parsed.get("reply", raw)).strip()
                acts = parsed.get("actions", [])
                if isinstance(acts, list):
                    actions_to_run = acts
        except Exception:
            # Fall back to raw text as reply, no actions
            pass

    # Execute actions
    action_results = []
    for act in actions_to_run:
        if not isinstance(act, dict):
            continue
        tool = act.get("tool")
        args = act.get("args") or {}
        if not tool:
            continue
        result = await _run_tool(user, tool, args)
        action_results.append(result)

    # Persist assistant turn
    assistant_msg = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "role": "assistant",
        "content": reply_text,
        "actions": action_results,
        "created_at": iso(now_utc()),
    }
    await db.agent_messages.insert_one(assistant_msg)
    assistant_msg.pop("_id", None)

    return {
        "assistant": assistant_msg,
        "actions": action_results,
        # Hints for the frontend on what to refresh
        "invalidate": sorted({
            {"create_task": "tasks", "update_task": "tasks", "break_down_goal": "goals",
             "add_note": "notes"}.get(a.get("tool"), "")
            for a in action_results if a.get("status") == "ok"
        } - {""}),
    }


@api.post("/agent/reflect-note")
async def reflect_note(payload: NoteReflectIn, user: dict = Depends(get_current_user)):
    note = await db.notes.find_one({"id": payload.note_id, "user_id": user["id"]}, {"_id": 0})
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Fast path: persist an already-generated reflection without re-calling the LLM.
    if payload.save and payload.reflection is not None:
        text = payload.reflection.strip()
        await db.notes.update_one(
            {"id": payload.note_id, "user_id": user["id"]},
            {"$set": {"reflection": text, "updated_at": iso(now_utc())}},
        )
        return {"reflection": text, "saved": True}

    ctx = build_user_context(user)
    system = (
        "You are Momentum reflecting on a personal note the user wrote. "
        "Read it carefully. Return a short, honest, warm response (150-250 words): "
        "name the emotion or pattern you notice, mirror what they seem to be working through, "
        "and offer ONE grounded question or next step tailored to their working style and mindset. "
        "Return PLAIN TEXT only — no JSON, no markdown headers."
    )
    prompt = (
        f"{ctx}\n\n"
        f"NOTE TITLE: {note.get('title','') or 'Untitled'}\n"
        f"NOTE CONTENT:\n{note['content']}\n"
    )
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"reflect-{payload.note_id}-{uuid.uuid4()}",
        system_message=system,
    ).with_model("anthropic", "claude-sonnet-4-6")
    reflection = ""
    try:
        async for ev in chat.stream_message(UserMessage(text=prompt)):
            if isinstance(ev, TextDelta):
                reflection += ev.content
            elif isinstance(ev, StreamDone):
                break
    except Exception as e:
        logger.exception("reflect-note failed")
        raise HTTPException(status_code=500, detail=f"AI error: {e}")

    reflection = reflection.strip()
    if payload.save:
        await db.notes.update_one(
            {"id": payload.note_id, "user_id": user["id"]},
            {"$set": {"reflection": reflection, "updated_at": iso(now_utc())}},
        )
    return {"reflection": reflection, "saved": payload.save}



# -------------------- Health --------------------
@api.get("/")
async def root():
    return {"status": "ok", "service": "momentum"}


# -------------------- Register --------------------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.tasks.create_index([("user_id", 1), ("status", 1)])
    await db.goals.create_index([("user_id", 1), ("status", 1)])
    await db.notes.create_index("user_id")
    await db.chat_messages.create_index([("user_id", 1), ("created_at", 1)])
    await db.agent_messages.create_index([("user_id", 1), ("created_at", 1)])
    # Seed default owner user for single-user mode (idempotent)
    existing = await db.users.find_one({"email": DEFAULT_USER_EMAIL})
    if not existing:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": DEFAULT_USER_EMAIL,
            "name": DEFAULT_USER_NAME,
            "password_hash": hash_password(uuid.uuid4().hex),
            "working_style": "",
            "mindset": "",
            "preferences": "",
            "created_at": iso(now_utc()),
        })
        logger.info("Seeded default owner user")
    logger.info("Startup complete")


@app.on_event("shutdown")
async def shutdown():
    client.close()
