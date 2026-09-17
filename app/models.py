"""Pydantic models.

Two kinds live here and the distinction matters:

- Request/response models, which FastAPI validates at the HTTP boundary.
- LLM output contracts (``*Result``), handed to Gemini as a response schema so
  a reply that doesn't fit the shape is rejected by the SDK before it reaches
  our code. Enumerated fields are `Literal[...]`, so the model cannot invent a
  priority or a status that the database would refuse.
"""

from typing import Literal

from pydantic import BaseModel, Field

Priority = Literal['low', 'medium', 'high']
TaskStatus = Literal['todo', 'in_progress', 'done']
GoalStatus = Literal['active', 'achieved', 'dropped']


# --- Profile ----------------------------------------------------------------
class ProfileIn(BaseModel):
    working_style: str = ''
    mindset: str = ''
    preferences: str = ''


# --- Goals ------------------------------------------------------------------
class GoalIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ''
    target_date: str | None = None


class GoalPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    target_date: str | None = None
    status: GoalStatus | None = None


# --- Tasks ------------------------------------------------------------------
class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ''
    priority: Priority = 'medium'
    estimated_minutes: int = Field(default=60, ge=5, le=480)
    due_date: str | None = None
    goal_id: int | None = None


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    priority: Priority | None = None
    status: TaskStatus | None = None
    estimated_minutes: int | None = Field(default=None, ge=5, le=480)
    due_date: str | None = None


# --- Notes ------------------------------------------------------------------
class NoteIn(BaseModel):
    title: str = ''
    content: str = Field(min_length=1)


# --- Chat -------------------------------------------------------------------
class ChatIn(BaseModel):
    message: str = Field(min_length=1)


# --- LLM output contracts ---------------------------------------------------
class SuggestedTask(BaseModel):
    """One task proposed by the breakdown call."""

    title: str = Field(max_length=200)
    description: str = ''
    priority: Priority = 'medium'
    estimated_minutes: int = Field(default=60, ge=5, le=480)


class BreakdownResult(BaseModel):
    """Structured-output contract for the goal-breakdown prompt."""

    tasks: list[SuggestedTask]


class PlannedItem(BaseModel):
    """One entry in a generated day plan.

    ``task_id`` refers to a task that already exists. The route verifies every
    id against the database before returning, so a hallucinated id is dropped
    rather than shown.
    """

    task_id: int
    reason: str = ''


class PlanDayResult(BaseModel):
    """Structured-output contract for the plan-my-day prompt."""

    focus: str
    items: list[PlannedItem]


class CoachResult(BaseModel):
    """Structured-output contract for the coach reply."""

    reply: str
