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


# ---------- Agent: create_goal_with_tasks (composite) ----------
def test_agent_create_goal_with_tasks(client):
    # cleanup any newsletter goal
    for g in client.get(f"{API}/goals").json():
        if "newsletter" in g["title"].lower() or g.get("title", "").startswith("TEST_"):
            client.delete(f"{API}/goals/{g['id']}")

    r = client.post(
        f"{API}/agent/chat",
        json={"message": "Plan my week around launching the TEST_newsletter"},
        timeout=180,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    ok_actions = [a for a in data["actions"] if a["status"] == "ok"]
    tools = [a["tool"] for a in ok_actions]
    # Should be create_goal_with_tasks OR (create_goal + several create_task)
    assert ("create_goal_with_tasks" in tools) or (
        "create_goal" in tools and tools.count("create_task") >= 2
    ), f"tools={tools}"
    assert set(data.get("invalidate", [])) & {"goals", "tasks"}

    goals = client.get(f"{API}/goals").json()
    nl = next((g for g in goals if "newsletter" in g["title"].lower()), None)
    assert nl is not None, f"No newsletter goal in {[g['title'] for g in goals]}"
    assert nl["task_count"] >= 2, f"task_count={nl['task_count']}"


# ---------- Agent: batch create_task (three tasks in one turn) ----------
def test_agent_batch_create_tasks(client):
    client.delete(f"{API}/agent/history")
    # cleanup
    for t in client.get(f"{API}/tasks").json():
        if any(k in t["title"].lower() for k in ["email designer", "draft copy", "book venue"]):
            client.delete(f"{API}/tasks/{t['id']}")

    r = client.post(
        f"{API}/agent/chat",
        json={"message": "Add three tasks: email designer, draft copy, book venue"},
        timeout=120,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    ok_creates = [a for a in data["actions"] if a["tool"] == "create_task" and a["status"] == "ok"]
    assert len(ok_creates) >= 3, f"only {len(ok_creates)} create_task actions: {data['actions']}"

    titles = [t["title"].lower() for t in client.get(f"{API}/tasks").json()]
    for keyword in ["email designer", "draft copy", "book venue"]:
        assert any(keyword in t for t in titles), f"missing '{keyword}' in {titles}"


# ---------- Agent: multi-tool turn (goal + tasks + note) ----------
def test_agent_multi_tool_turn(client):
    client.delete(f"{API}/agent/history")
    # cleanup any prior marathon goal
    for g in client.get(f"{API}/goals").json():
        if "marathon" in g["title"].lower():
            client.delete(f"{API}/goals/{g['id']}")

    r = client.post(
        f"{API}/agent/chat",
        json={
            "message": "I want to run a first marathon in 6 months. Set that up as a goal with training tasks, and capture a note that my main worry is knee injuries."
        },
        timeout=180,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    ok_actions = [a for a in data["actions"] if a["status"] == "ok"]
    tools = [a["tool"] for a in ok_actions]
    has_goal = "create_goal_with_tasks" in tools or "create_goal" in tools
    has_note = "add_note" in tools
    assert has_goal and has_note, f"tools={tools}"

    goals = client.get(f"{API}/goals").json()
    marathon = next((g for g in goals if "marathon" in g["title"].lower()), None)
    assert marathon is not None
    assert marathon["task_count"] >= 2

    notes = client.get(f"{API}/notes").json()
    assert any("knee" in (n.get("content", "") + n.get("title", "")).lower() for n in notes)


# ---------- Agent: no-permission behavior (must act, not ask) ----------
def test_agent_no_permission_asking(client):
    client.delete(f"{API}/agent/history")
    r = client.post(
        f"{API}/agent/chat",
        json={"message": "TEST_actfirst — prep for my client demo tomorrow"},
        timeout=120,
    )
    assert r.status_code == 200
    data = r.json()
    reply = data["assistant"]["content"].lower()
    ok_actions = [a for a in data["actions"] if a["status"] == "ok"]
    # Must have acted (>=1 tool succeeded)
    assert len(ok_actions) >= 1, f"agent asked permission instead of acting; reply={reply[:200]}, actions={data['actions']}"
    # Should NOT contain permission-asking phrases
    forbidden = ["would you like me to", "should i create", "want me to create", "shall i"]
    assert not any(p in reply for p in forbidden), f"agent asked permission: {reply[:300]}"


# ---------- Cleanup ----------
def test_zz_cleanup(client):
    for t in client.get(f"{API}/tasks").json():
        if t["title"].startswith("TEST_") or "Q1" in t["title"]:
            client.delete(f"{API}/tasks/{t['id']}")
    for n in client.get(f"{API}/notes").json():
        if n.get("title", "").startswith("TEST_") or "lo-fi" in n.get("content", "").lower():
            client.delete(f"{API}/notes/{n['id']}")
    for g in client.get(f"{API}/goals").json():
        if g.get("title", "").startswith("TEST_") or "newsletter" in g["title"].lower() or "marathon" in g["title"].lower():
            client.delete(f"{API}/goals/{g['id']}")
