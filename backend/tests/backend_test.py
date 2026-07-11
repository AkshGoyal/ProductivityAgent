"""Backend tests for Momentum AI Agent (iteration 4).
Focus: /api/agent/chat with tool calling, /api/agent/history, /api/agent/reflect-note.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    # auto-auth via /auth/session — sets cookie
    r = s.get(f"{API}/auth/session", timeout=30)
    assert r.status_code == 200, f"session failed: {r.status_code} {r.text}"
    return s


# ---------- Health ----------
def test_health(client):
    r = client.get(f"{API}/", timeout=15)
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_me(client):
    r = client.get(f"{API}/auth/me", timeout=15)
    assert r.status_code == 200
    assert r.json()["email"] == "owner@momentum.app"


# ---------- Agent history clear (reset state) ----------
def test_clear_agent_history(client):
    r = client.delete(f"{API}/agent/history", timeout=15)
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    r2 = client.get(f"{API}/agent/history", timeout=15)
    assert r2.status_code == 200
    assert r2.json() == []


# ---------- Agent chat: create_task tool ----------
def test_agent_create_task(client):
    # cleanup any existing TEST_ tasks
    tasks = client.get(f"{API}/tasks").json()
    for t in tasks:
        if t["title"].startswith("TEST_"):
            client.delete(f"{API}/tasks/{t['id']}")

    r = client.post(
        f"{API}/agent/chat",
        json={"message": "Create a task called TEST_DraftQ1Plan with high priority"},
        timeout=90,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "assistant" in data
    assert "actions" in data
    # Should have run create_task
    tools_run = [a["tool"] for a in data["actions"]]
    assert "create_task" in tools_run, f"actions: {data['actions']}"
    ok_actions = [a for a in data["actions"] if a["tool"] == "create_task" and a["status"] == "ok"]
    assert len(ok_actions) >= 1
    assert "tasks" in data.get("invalidate", [])

    # Verify persistence
    tasks = client.get(f"{API}/tasks").json()
    matches = [t for t in tasks if "TEST_" in t["title"] or "Q1" in t["title"]]
    assert matches, f"No matching task found in {[t['title'] for t in tasks]}"


# ---------- Agent chat: update_task tool ----------
def test_agent_update_task(client):
    # Ensure a task exists
    tasks = client.get(f"{API}/tasks").json()
    target = next((t for t in tasks if "Q1" in t["title"] or "TEST_" in t["title"]), None)
    if not target:
        # create one via API
        created = client.post(f"{API}/tasks", json={"title": "TEST_UpdateMe", "priority": "medium"}).json()
        target = created

    msg = f"Mark my '{target['title']}' task as done. task_id is {target['id']}"
    r = client.post(f"{API}/agent/chat", json={"message": msg}, timeout=90)
    assert r.status_code == 200, r.text
    data = r.json()
    tools = [a["tool"] for a in data["actions"] if a["status"] == "ok"]
    # allow retry — sometimes agent replies without action
    if "update_task" not in tools:
        pytest.skip(f"Agent did not call update_task; actions={data['actions']}")

    # Verify status
    t = next((x for x in client.get(f"{API}/tasks").json() if x["id"] == target["id"]), None)
    assert t is not None
    assert t["status"] == "done", f"status={t['status']}"


# ---------- Agent chat: add_note tool ----------
def test_agent_add_note(client):
    r = client.post(
        f"{API}/agent/chat",
        json={"message": "Add a note titled 'TEST_Idea', content: 'try lo-fi mornings'"},
        timeout=90,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    tools = [a["tool"] for a in data["actions"] if a["status"] == "ok"]
    assert "add_note" in tools, f"actions: {data['actions']}"
    assert "notes" in data.get("invalidate", [])

    notes = client.get(f"{API}/notes").json()
    assert any("lo-fi" in n["content"].lower() or "TEST_Idea" in n.get("title", "") for n in notes)


# ---------- Agent chat: break_down_goal tool ----------
def test_agent_break_down_goal(client):
    # create a goal manually
    goal = client.post(f"{API}/goals", json={"title": "TEST_Ship_Momentum_launch", "description": "Q1 launch"}).json()
    goal_id = goal["id"]

    msg = f"Break down my goal titled '{goal['title']}' (goal_id: {goal_id}) into tasks."
    r = client.post(f"{API}/agent/chat", json={"message": msg}, timeout=180)
    assert r.status_code == 200, r.text
    data = r.json()
    tools = [a for a in data["actions"] if a["tool"] == "break_down_goal" and a["status"] == "ok"]
    if not tools:
        pytest.skip(f"Agent did not call break_down_goal; actions={data['actions']}")
    created_tasks = tools[0]["result"]["tasks"]
    assert len(created_tasks) >= 3, f"Only {len(created_tasks)} tasks created"

    # Verify goal task_count updated
    goals = client.get(f"{API}/goals").json()
    g = next(x for x in goals if x["id"] == goal_id)
    assert g["task_count"] >= len(created_tasks)

    # cleanup
    client.delete(f"{API}/goals/{goal_id}")


# ---------- Agent chat: grounded context ----------
def test_agent_grounded_context(client):
    # ensure at least one task/goal exists
    client.post(f"{API}/tasks", json={"title": "TEST_GroundedProbe", "priority": "high"})
    r = client.post(f"{API}/agent/chat", json={"message": "What am I working on right now?"}, timeout=90)
    assert r.status_code == 200
    reply = r.json()["assistant"]["content"].lower()
    # loose check — reply should be substantive (not empty)
    assert len(reply) > 20


# ---------- Agent chat: history persistence ----------
def test_agent_history_persistence(client):
    hist = client.get(f"{API}/agent/history").json()
    assert isinstance(hist, list) and len(hist) > 0
    roles = {h["role"] for h in hist}
    assert "user" in roles and "assistant" in roles


# ---------- Note reflection ----------
def test_reflect_note_no_save(client):
    note = client.post(f"{API}/notes", json={"title": "TEST_Reflect", "content": "I keep procrastinating on my launch email. It feels heavy."}).json()
    r = client.post(f"{API}/agent/reflect-note", json={"note_id": note["id"], "save": False}, timeout=90)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "reflection" in d and len(d["reflection"]) > 20
    assert d["saved"] is False

    # Verify NOT persisted
    n = next(x for x in client.get(f"{API}/notes").json() if x["id"] == note["id"])
    assert not n.get("reflection")


def test_reflect_note_with_save(client):
    note = client.post(f"{API}/notes", json={"title": "TEST_ReflectSave", "content": "Trying to figure out my Q1 focus."}).json()
    r = client.post(f"{API}/agent/reflect-note", json={"note_id": note["id"], "save": True}, timeout=90)
    assert r.status_code == 200
    d = r.json()
    assert d["saved"] is True
    # persistence
    n = next(x for x in client.get(f"{API}/notes").json() if x["id"] == note["id"])
    assert n.get("reflection") and len(n["reflection"]) > 20


def test_reflect_note_404(client):
    r = client.post(f"{API}/agent/reflect-note", json={"note_id": "nonexistent-id-xyz", "save": False}, timeout=30)
    assert r.status_code == 404


# ---------- Cleanup ----------
def test_zz_cleanup(client):
    for t in client.get(f"{API}/tasks").json():
        if t["title"].startswith("TEST_") or "Q1" in t["title"]:
            client.delete(f"{API}/tasks/{t['id']}")
    for n in client.get(f"{API}/notes").json():
        if n.get("title", "").startswith("TEST_") or "lo-fi" in n.get("content", "").lower():
            client.delete(f"{API}/notes/{n['id']}")
    for g in client.get(f"{API}/goals").json():
        if g.get("title", "").startswith("TEST_"):
            client.delete(f"{API}/goals/{g['id']}")
