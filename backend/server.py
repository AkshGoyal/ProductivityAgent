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


class ChatIn(BaseModel):
    message: str
    session_id: Optional[str] = None


class GoalBreakdownIn(BaseModel):
    goal_id: str


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
