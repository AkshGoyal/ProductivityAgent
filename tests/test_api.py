"""Route behaviour, including the guards on AI-generated output."""

from app import api, llm, models, repo
from tests.conftest import FakeLLMClient


def _fake_llm(monkeypatch, *responses):
    """Point llm.call at a queued fake client for the duration of a test."""
    client = FakeLLMClient(*responses)
    original = llm.call
    monkeypatch.setattr(
        api.llm, 'call', lambda *a, **kw: original(*a, client=client, **kw)
    )
    return client


def test_crud_round_trip_for_tasks(client):
    created = client.post('/api/tasks', json={'title': 'Draft the deck', 'priority': 'high'})
    assert created.status_code == 201
    task_id = created.json()['id']

    assert client.get('/api/tasks').json()[0]['title'] == 'Draft the deck'

    patched = client.patch(f'/api/tasks/{task_id}', json={'status': 'done'})
    assert patched.json()['status'] == 'done'

    assert client.delete(f'/api/tasks/{task_id}').status_code == 204
    assert client.get('/api/tasks').json() == []


def test_task_rejects_an_unknown_goal_id(client):
    response = client.post('/api/tasks', json={'title': 'Orphan', 'goal_id': 4242})
    assert response.status_code == 400


def test_task_rejects_an_invalid_priority(client):
    """Enumerated fields are Literal types, so FastAPI refuses at the boundary."""
    response = client.post('/api/tasks', json={'title': 'x', 'priority': 'urgent'})
    assert response.status_code == 422


def test_patching_a_missing_task_is_404(client):
    assert client.patch('/api/tasks/999', json={'status': 'done'}).status_code == 404


def test_breakdown_stores_the_generated_tasks(client, conn, monkeypatch):
    goal = repo.create_goal(conn, 'Launch the newsletter', 'weekly, technical', None)
    _fake_llm(
        monkeypatch,
        models.BreakdownResult(
            tasks=[
                models.SuggestedTask(title='Pick the publishing platform', estimated_minutes=30),
                models.SuggestedTask(title='Draft issue one', priority='high', estimated_minutes=90),
            ]
        ),
    )

    response = client.post(f"/api/goals/{goal['id']}/breakdown")

    assert response.status_code == 200
    assert [t['title'] for t in response.json()['tasks']] == [
        'Pick the publishing platform',
        'Draft issue one',
    ]
    stored = repo.list_tasks(conn, goal_id=goal['id'])
    assert len(stored) == 2
    assert all(t['goal_id'] == goal['id'] for t in stored)


def test_breakdown_on_a_missing_goal_is_404(client):
    assert client.post('/api/goals/999/breakdown').status_code == 404


def test_breakdown_reports_an_empty_result_instead_of_silently_succeeding(
    client, conn, monkeypatch
):
    goal = repo.create_goal(conn, 'Vague', '', None)
    _fake_llm(monkeypatch, models.BreakdownResult(tasks=[]))

    assert client.post(f"/api/goals/{goal['id']}/breakdown").status_code == 502


def test_plan_day_drops_task_ids_the_model_invented(client, conn, monkeypatch):
    """The core guard: a hallucinated id must never reach the UI."""
    real = repo.create_task(conn, title='Real task')
    _fake_llm(
        monkeypatch,
        models.PlanDayResult(
            focus='Ship the real thing',
            items=[
                models.PlannedItem(task_id=real['id'], reason='highest leverage'),
                models.PlannedItem(task_id=98765, reason='does not exist'),
            ],
        ),
    )

    body = client.post('/api/plan-day').json()

    assert len(body['items']) == 1
    assert body['items'][0]['task']['id'] == real['id']


def test_plan_day_with_nothing_open_does_not_call_the_model(client):
    body = client.post('/api/plan-day').json()
    assert body['items'] == []
    assert 'add a task' in body['focus']


def test_chat_persists_both_turns(client, conn, monkeypatch):
    _fake_llm(monkeypatch, models.CoachResult(reply='Start with the smallest one.'))

    response = client.post('/api/chat', json={'message': 'where do I start?'})

    assert response.json()['content'] == 'Start with the smallest one.'
    history = repo.recent_chat(conn)
    assert [m['role'] for m in history] == ['user', 'assistant']


def test_llm_failure_surfaces_as_502_not_500(client, conn, monkeypatch):
    goal = repo.create_goal(conn, 'Anything', '', None)

    def explode(*_args, **_kwargs):
        raise llm.LLMError('model overloaded')

    monkeypatch.setattr(api.llm, 'call', explode)

    assert client.post(f"/api/goals/{goal['id']}/breakdown").status_code == 502


def test_stats_endpoint(client, conn):
    done = repo.create_task(conn, title='done one')
    repo.create_task(conn, title='open one')
    repo.update_task(conn, done['id'], {'status': 'done'})

    body = client.get('/api/stats').json()
    assert body['tasks_total'] == 2
    assert body['completion_rate'] == 50
