"""Central configuration — the one place for settings.

The API key comes from the environment only and is never written to the
database or committed. Model names and paths live here so they change in one
place.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --- LLM --------------------------------------------------------------------
# The google-genai SDK reads GEMINI_API_KEY from the environment itself.
API_KEY_ENV_VAR = "GEMINI_API_KEY"
MODEL = os.environ.get("PLANMYDAY_MODEL", "gemini-3.5-flash")

# Generation tasks spend output tokens on internal reasoning too, so the cap
# needs more headroom than a plain extraction call would.
MAX_OUTPUT_TOKENS = int(os.environ.get("PLANMYDAY_MAX_TOKENS", "8192"))

# --- Paths ------------------------------------------------------------------
DB_PATH = Path(os.environ.get("PLANMYDAY_DB", ROOT / "planmyday.db"))
PROMPTS_DIR = ROOT / "app" / "prompts"
STATIC_DIR = ROOT / "static"

# --- Server -----------------------------------------------------------------
# Binds to loopback by default: this is a single-user local tool, not a hosted
# service. There is no auth layer, so it must not listen on a public interface.
HOST = os.environ.get("PLANMYDAY_HOST", "127.0.0.1")
PORT = int(os.environ.get("PLANMYDAY_PORT", "8000"))

# How many goals/tasks/notes to feed the model as context. Bounded so prompts
# stay a predictable size as the database grows.
CONTEXT_TASK_LIMIT = 30
CONTEXT_GOAL_LIMIT = 15
CONTEXT_NOTE_LIMIT = 5
CONTEXT_CHAT_TURNS = 12


def api_key_present() -> bool:
    """True if a Gemini API key is available in the environment."""
    return bool(os.environ.get(API_KEY_ENV_VAR))
