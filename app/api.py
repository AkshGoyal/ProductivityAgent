"""HTTP routes.

Everything lives under /api. The three AI-backed routes (breakdown, plan-day,
chat) all follow the same shape: build bounded context, make one schema-checked
LLM call through `llm.call`, then verify the result against the database before
anything is written or returned.
"""

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app import context, llm, models, repo
from app.db import connect, migrate

router = APIRouter(prefix='/api')

_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    """One shared connection: single user, single process, SQLite."""
    global _conn
    if _conn is None:
        _conn = connect()
        migrate(_conn)
    return _conn


def set_conn(conn: sqlite3.Connection | None) -> None:
    """Swap the connection — used by the test fixtures."""
    global _conn
    _conn = conn


Conn = Depends(get_conn)


# --- Profile ----------------------------------------------------------------
@router.get('/profile')
def read_profile(conn: sqlite3.Connection = Conn):
    return repo.get_profile(conn)


@router.put('/profile')
def write_profile(payload: models.ProfileIn, conn: sqlite3.Connection = Conn):
    return repo.update_profile(
        conn, payload.working_style, payload.mindset, payload.preferences
    )


# --- Goals ------------------------------------------------------------------
@router.get('/goals')
def read_goals(status: str | None = None, conn: sqlite3.Connection = Conn):
    return repo.list_goals(conn, status)


@router.post('/goals', status_code=201)
def add_goal(payload: models.GoalIn, conn: sqlite3.Connection = Conn):
    return repo.create_goal(conn, payload.title, payload.description, payload.target_date)


@router.patch('/goals/{goal_id}')
def patch_goal(goal_id: int, payload: models.GoalPatch, conn: sqlite3.Connection = Conn):
    if repo.get_goal(conn, goal_id) is None:
        raise HTTPException(404, 'goal not found')
    return repo.update_goal(conn, goal_id, payload.model_dump(exclude_unset=True))


@router.delete('/goals/{goal_id}', status_code=204)
def remove_goal(goal_id: int, conn: sqlite3.Connection = Conn):
    if not repo.delete_goal(conn, goal_id):
        raise HTTPException(404, 'goal not found')


@router.post('/goals/{goal_id}/breakdown')
def breakdown_goal(goal_id: int, conn: sqlite3.Connection = Conn):
    """Turn a goal into 5-8 atomic tasks and store them."""
    goal = repo.get_goal(conn, goal_id)
    if goal is None:
        raise HTTPException(404, 'goal not found')

    existing = repo.list_tasks(conn, goal_id=goal_id)

    try:
        result = llm.call(
            'breakdown_goal',
            models.BreakdownResult,
            profile=context.profile_block(conn),
            title=goal['title'],
            description=goal['description'] or '(none given)',
            target_date=goal['target_date'] or 'not set',
            existing_tasks=context.tasks_block(existing),
        )
    except llm.LLMError as exc:
        raise HTTPException(502, str(exc)) from exc

    if not result.tasks:
        raise HTTPException(502, 'the model returned no tasks — try rewording the goal')

    created = [
        repo.create_task(
            conn,
            title=task.title,
            description=task.description,
            priority=task.priority,
            estimated_minutes=task.estimated_minutes,
            goal_id=goal_id,
        )
        for task in result.tasks
    ]
    return {'goal': repo.get_goal(conn, goal_id), 'tasks': created}


# --- Tasks ------------------------------------------------------------------
@router.get('/tasks')
def read_tasks(
    status: str | None = None, goal_id: int | None = None, conn: sqlite3.Connection = Conn
):
    return repo.list_tasks(conn, status, goal_id)


@router.post('/tasks', status_code=201)
def add_task(payload: models.TaskIn, conn: sqlite3.Connection = Conn):
    if payload.goal_id is not None and repo.get_goal(conn, payload.goal_id) is None:
        raise HTTPException(400, 'goal_id does not exist')
    return repo.create_task(
        conn,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        estimated_minutes=payload.estimated_minutes,
        due_date=payload.due_date,
        goal_id=payload.goal_id,
    )


@router.patch('/tasks/{task_id}')
def patch_task(task_id: int, payload: models.TaskPatch, conn: sqlite3.Connection = Conn):
    if repo.get_task(conn, task_id) is None:
        raise HTTPException(404, 'task not found')
    return repo.update_task(conn, task_id, payload.model_dump(exclude_unset=True))


@router.delete('/tasks/{task_id}', status_code=204)
def remove_task(task_id: int, conn: sqlite3.Connection = Conn):
    if not repo.delete_task(conn, task_id):
        raise HTTPException(404, 'task not found')


# --- Notes ------------------------------------------------------------------
@router.get('/notes')
def read_notes(conn: sqlite3.Connection = Conn):
    return repo.list_notes(conn)


@router.post('/notes', status_code=201)
def add_note(payload: models.NoteIn, conn: sqlite3.Connection = Conn):
    return repo.create_note(conn, payload.title, payload.content)


@router.delete('/notes/{note_id}', status_code=204)
def remove_note(note_id: int, conn: sqlite3.Connection = Conn):
    if not repo.delete_note(conn, note_id):
        raise HTTPException(404, 'note not found')


# --- Plan my day ------------------------------------------------------------
@router.post('/plan-day')
def plan_day(capacity: int = 240, conn: sqlite3.Connection = Conn):
    """Pick and order today's work from the open tasks.

    The model returns task ids. Every id is checked against the database and
    anything it didn't recognise is dropped, so a hallucinated id can never
    reach the UI.
    """
    tasks = repo.open_tasks(conn)
    if not tasks:
        return {'focus': 'Nothing open — add a task or break down a goal first.', 'items': []}

    try:
        result = llm.call(
            'plan_day',
            models.PlanDayResult,
            profile=context.profile_block(conn),
            today=date.today().isoformat(),
            capacity=capacity,
            goals=context.goals_block(repo.list_goals(conn, status='active')),
            tasks=context.tasks_block(tasks),
        )
    except llm.LLMError as exc:
        raise HTTPException(502, str(exc)) from exc

    known = {task['id']: task for task in tasks}
    items = [
        {'task': known[item.task_id], 'reason': item.reason}
        for item in result.items
        if item.task_id in known
    ]
    return {'focus': result.focus, 'items': items}


# --- Coach chat -------------------------------------------------------------
@router.get('/chat')
def read_chat(conn: sqlite3.Connection = Conn):
    return repo.recent_chat(conn, turns=100)


@router.delete('/chat', status_code=204)
def clear_chat(conn: sqlite3.Connection = Conn):
    repo.clear_chat(conn)


@router.post('/chat')
def chat(payload: models.ChatIn, conn: sqlite3.Connection = Conn):
    """One coach turn, grounded in the current tasks, goals and notes."""
    history = context.history_block(conn)
    repo.add_chat_message(conn, 'user', payload.message)

    try:
        result = llm.call(
            'coach_chat',
            models.CoachResult,
            profile=context.profile_block(conn),
            goals=context.goals_block(repo.list_goals(conn, status='active')),
            tasks=context.tasks_block(repo.open_tasks(conn)),
            notes=context.notes_block(conn),
            history=history,
            message=payload.message,
        )
    except llm.LLMError as exc:
        raise HTTPException(502, str(exc)) from exc

    return repo.add_chat_message(conn, 'assistant', result.reply)


# --- Stats ------------------------------------------------------------------
@router.get('/stats')
def read_stats(conn: sqlite3.Connection = Conn):
    return repo.stats(conn)
