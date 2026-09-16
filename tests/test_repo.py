"""Storage behaviour."""

from app import repo


def test_profile_starts_empty_and_round_trips(conn):
    assert repo.get_profile(conn)['working_style'] == ''
    updated = repo.update_profile(conn, 'deep work mornings', 'bias to ship', 'no meetings before 11')
    assert updated['working_style'] == 'deep work mornings'
    assert repo.get_profile(conn)['mindset'] == 'bias to ship'


def test_goal_progress_counts_only_its_own_tasks(conn):
    goal = repo.create_goal(conn, 'Ship v1', '', None)
    other = repo.create_goal(conn, 'Unrelated', '', None)
    repo.create_task(conn, title='A', goal_id=goal['id'])
    done = repo.create_task(conn, title='B', goal_id=goal['id'])
    repo.create_task(conn, title='C', goal_id=other['id'])
    repo.update_task(conn, done['id'], {'status': 'done'})

    goals = {g['id']: g for g in repo.list_goals(conn)}
    assert goals[goal['id']]['task_total'] == 2
    assert goals[goal['id']]['task_done'] == 1
    assert goals[other['id']]['task_total'] == 1


def test_deleting_a_goal_orphans_its_tasks_rather_than_deleting_them(conn):
    """Losing a goal shouldn't silently destroy the work logged under it."""
    goal = repo.create_goal(conn, 'Temporary', '', None)
    task = repo.create_task(conn, title='Survives', goal_id=goal['id'])

    repo.delete_goal(conn, goal['id'])

    survivor = repo.get_task(conn, task['id'])
    assert survivor is not None
    assert survivor['goal_id'] is None


def test_open_tasks_are_ordered_high_priority_first(conn):
    repo.create_task(conn, title='low', priority='low')
    repo.create_task(conn, title='high', priority='high')
    repo.create_task(conn, title='medium', priority='medium')
    done = repo.create_task(conn, title='done', priority='high')
    repo.update_task(conn, done['id'], {'status': 'done'})

    titles = [t['title'] for t in repo.open_tasks(conn)]
    assert titles == ['high', 'medium', 'low']


def test_update_task_ignores_fields_that_are_not_allowed(conn):
    task = repo.create_task(conn, title='Original')
    repo.update_task(conn, task['id'], {'id': 999, 'title': 'Renamed'})
    assert repo.get_task(conn, task['id'])['title'] == 'Renamed'
    assert repo.get_task(conn, 999) is None


def test_stats_reports_completion_rate(conn):
    a = repo.create_task(conn, title='a')
    repo.create_task(conn, title='b')
    repo.update_task(conn, a['id'], {'status': 'done'})

    result = repo.stats(conn)
    assert result['tasks_total'] == 2
    assert result['tasks_done'] == 1
    assert result['completion_rate'] == 50


def test_recent_chat_returns_oldest_first(conn):
    repo.add_chat_message(conn, 'user', 'first')
    repo.add_chat_message(conn, 'assistant', 'second')
    repo.add_chat_message(conn, 'user', 'third')

    assert [m['content'] for m in repo.recent_chat(conn)] == ['first', 'second', 'third']
