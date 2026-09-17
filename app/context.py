"""Turning database rows into the text blocks the prompts interpolate.

Kept separate from the routes so the shape of what the model sees is defined in
one place and is easy to test. Every block is built from a bounded query, so
prompt size stays predictable as the database grows.
"""

import sqlite3
from typing import Any

from app import config, repo


def profile_block(conn: sqlite3.Connection) -> str:
    profile = repo.get_profile(conn)
    parts = []
    if profile.get('working_style'):
        parts.append(f"Working style: {profile['working_style']}")
    if profile.get('mindset'):
        parts.append(f"Mindset: {profile['mindset']}")
    if profile.get('preferences'):
        parts.append(f"Preferences: {profile['preferences']}")
    return '\n'.join(parts) if parts else 'No profile set yet.'


def tasks_block(tasks: list[dict[str, Any]]) -> str:
    if not tasks:
        return 'None.'
    return '\n'.join(
        f"[id {t['id']}] {t['title']} "
        f"(priority: {t['priority']}, est: {t['estimated_minutes']}m"
        + (f", due: {t['due_date']}" if t.get('due_date') else '')
        + ')'
        for t in tasks
    )


def goals_block(goals: list[dict[str, Any]]) -> str:
    if not goals:
        return 'None.'
    lines = []
    for goal in goals:
        line = f"[id {goal['id']}] {goal['title']}"
        if goal.get('target_date'):
            line += f" (target: {goal['target_date']})"
        if goal.get('task_total'):
            line += f" — {goal.get('task_done', 0)}/{goal['task_total']} tasks done"
        lines.append(line)
    return '\n'.join(lines)


def notes_block(conn: sqlite3.Connection) -> str:
    notes = repo.list_notes(conn, limit=config.CONTEXT_NOTE_LIMIT)
    if not notes:
        return 'None.'
    return '\n'.join(
        f"- {n['created_at'][:10]} {n['title'] or 'Untitled'}: {n['content'][:400]}" for n in notes
    )


def history_block(conn: sqlite3.Connection) -> str:
    messages = repo.recent_chat(conn)
    if not messages:
        return 'This is the first message.'
    return '\n'.join(f"{m['role'].upper()}: {m['content']}" for m in messages)
