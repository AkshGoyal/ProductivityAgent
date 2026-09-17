"""Data access. Every SQL statement in the project lives here."""

import sqlite3
from typing import Any

from app import config


def _rows(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(row) for row in cursor.fetchall()]


# --- Profile ----------------------------------------------------------------
def get_profile(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute('SELECT * FROM profile WHERE id = 1').fetchone()
    return dict(row) if row else {}


def update_profile(
    conn: sqlite3.Connection, working_style: str, mindset: str, preferences: str
) -> dict[str, Any]:
    conn.execute(
        """UPDATE profile
           SET working_style = ?, mindset = ?, preferences = ?,
               updated_at = datetime('now')
         WHERE id = 1""",
        (working_style, mindset, preferences),
    )
    conn.commit()
    return get_profile(conn)


# --- Goals ------------------------------------------------------------------
def create_goal(
    conn: sqlite3.Connection, title: str, description: str, target_date: str | None
) -> dict[str, Any]:
    cur = conn.execute(
        'INSERT INTO goal (title, description, target_date) VALUES (?, ?, ?)',
        (title, description, target_date),
    )
    conn.commit()
    return get_goal(conn, int(cur.lastrowid))


def get_goal(conn: sqlite3.Connection, goal_id: int) -> dict[str, Any] | None:
    row = conn.execute('SELECT * FROM goal WHERE id = ?', (goal_id,)).fetchone()
    return dict(row) if row else None


def list_goals(conn: sqlite3.Connection, status: str | None = None) -> list[dict[str, Any]]:
    if status:
        cur = conn.execute(
            'SELECT * FROM goal WHERE status = ? ORDER BY created_at DESC', (status,)
        )
    else:
        cur = conn.execute('SELECT * FROM goal ORDER BY created_at DESC')
    goals = _rows(cur)
    for goal in goals:
        counts = conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done
                 FROM task WHERE goal_id = ?""",
            (goal['id'],),
        ).fetchone()
        goal['task_total'] = counts['total'] or 0
        goal['task_done'] = counts['done'] or 0
    return goals


def update_goal(conn: sqlite3.Connection, goal_id: int, fields: dict[str, Any]) -> dict[str, Any] | None:
    if not fields:
        return get_goal(conn, goal_id)
    allowed = {'title', 'description', 'target_date', 'status'}
    sets = [f'{k} = ?' for k in fields if k in allowed]
    if not sets:
        return get_goal(conn, goal_id)
    values = [fields[k] for k in fields if k in allowed]
    conn.execute(
        f"UPDATE goal SET {', '.join(sets)}, updated_at = datetime('now') WHERE id = ?",
        (*values, goal_id),
    )
    conn.commit()
    return get_goal(conn, goal_id)


def delete_goal(conn: sqlite3.Connection, goal_id: int) -> bool:
    cur = conn.execute('DELETE FROM goal WHERE id = ?', (goal_id,))
    conn.commit()
    return cur.rowcount > 0


# --- Tasks ------------------------------------------------------------------
def create_task(
    conn: sqlite3.Connection,
    *,
    title: str,
    description: str = '',
    priority: str = 'medium',
    estimated_minutes: int = 60,
    due_date: str | None = None,
    goal_id: int | None = None,
) -> dict[str, Any]:
    cur = conn.execute(
        """INSERT INTO task
               (title, description, priority, estimated_minutes, due_date, goal_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (title, description, priority, estimated_minutes, due_date, goal_id),
    )
    conn.commit()
    return get_task(conn, int(cur.lastrowid))


def get_task(conn: sqlite3.Connection, task_id: int) -> dict[str, Any] | None:
    row = conn.execute('SELECT * FROM task WHERE id = ?', (task_id,)).fetchone()
    return dict(row) if row else None


def list_tasks(
    conn: sqlite3.Connection, status: str | None = None, goal_id: int | None = None
) -> list[dict[str, Any]]:
    clauses, params = [], []
    if status:
        clauses.append('status = ?')
        params.append(status)
    if goal_id is not None:
        clauses.append('goal_id = ?')
        params.append(goal_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ''
    return _rows(
        conn.execute(
            f"""SELECT * FROM task {where}
                ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                         created_at DESC""",
            params,
        )
    )


def open_tasks(conn: sqlite3.Connection, limit: int = config.CONTEXT_TASK_LIMIT) -> list[dict[str, Any]]:
    return _rows(
        conn.execute(
            """SELECT * FROM task WHERE status != 'done'
                ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                         created_at DESC
                LIMIT ?""",
            (limit,),
        )
    )


def update_task(conn: sqlite3.Connection, task_id: int, fields: dict[str, Any]) -> dict[str, Any] | None:
    allowed = {'title', 'description', 'priority', 'status', 'estimated_minutes', 'due_date'}
    sets = [f'{k} = ?' for k in fields if k in allowed]
    if not sets:
        return get_task(conn, task_id)
    values = [fields[k] for k in fields if k in allowed]
    conn.execute(
        f"UPDATE task SET {', '.join(sets)}, updated_at = datetime('now') WHERE id = ?",
        (*values, task_id),
    )
    conn.commit()
    return get_task(conn, task_id)


def delete_task(conn: sqlite3.Connection, task_id: int) -> bool:
    cur = conn.execute('DELETE FROM task WHERE id = ?', (task_id,))
    conn.commit()
    return cur.rowcount > 0


# --- Notes ------------------------------------------------------------------
def create_note(conn: sqlite3.Connection, title: str, content: str) -> dict[str, Any]:
    cur = conn.execute('INSERT INTO note (title, content) VALUES (?, ?)', (title, content))
    conn.commit()
    row = conn.execute('SELECT * FROM note WHERE id = ?', (cur.lastrowid,)).fetchone()
    return dict(row)


def list_notes(conn: sqlite3.Connection, limit: int | None = None) -> list[dict[str, Any]]:
    if limit:
        return _rows(conn.execute('SELECT * FROM note ORDER BY created_at DESC LIMIT ?', (limit,)))
    return _rows(conn.execute('SELECT * FROM note ORDER BY created_at DESC'))


def delete_note(conn: sqlite3.Connection, note_id: int) -> bool:
    cur = conn.execute('DELETE FROM note WHERE id = ?', (note_id,))
    conn.commit()
    return cur.rowcount > 0


# --- Chat -------------------------------------------------------------------
def add_chat_message(conn: sqlite3.Connection, role: str, content: str) -> dict[str, Any]:
    cur = conn.execute('INSERT INTO chat_message (role, content) VALUES (?, ?)', (role, content))
    conn.commit()
    row = conn.execute('SELECT * FROM chat_message WHERE id = ?', (cur.lastrowid,)).fetchone()
    return dict(row)


def recent_chat(conn: sqlite3.Connection, turns: int = config.CONTEXT_CHAT_TURNS) -> list[dict[str, Any]]:
    rows = _rows(
        conn.execute('SELECT * FROM chat_message ORDER BY created_at DESC, id DESC LIMIT ?', (turns,))
    )
    return list(reversed(rows))


def clear_chat(conn: sqlite3.Connection) -> None:
    conn.execute('DELETE FROM chat_message')
    conn.commit()


# --- Stats ------------------------------------------------------------------
def stats(conn: sqlite3.Connection) -> dict[str, Any]:
    task_counts = conn.execute(
        """SELECT COUNT(*) AS total,
                  SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done,
                  SUM(CASE WHEN status != 'done' THEN 1 ELSE 0 END) AS open
             FROM task"""
    ).fetchone()
    total = task_counts['total'] or 0
    done = task_counts['done'] or 0
    return {
        'tasks_total': total,
        'tasks_done': done,
        'tasks_open': task_counts['open'] or 0,
        'completion_rate': round(done / total * 100) if total else 0,
        'goals_active': conn.execute(
            "SELECT COUNT(*) AS n FROM goal WHERE status = 'active'"
        ).fetchone()['n'],
        'notes_total': conn.execute('SELECT COUNT(*) AS n FROM note').fetchone()['n'],
    }
