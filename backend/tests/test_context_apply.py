"""Approved context is an explicit, atomic planning edit."""
import pytest
from sqlalchemy.orm import Session
from app.models.memory import PlanningMemory
from tests.test_memory import actors, base_plan, post


def memory(client, owner, value, key='Preference', **extra):
    assert client.put('/api/memory/consent', headers=owner, json={'enabled': True}).status_code == 200
    return post(client, '/api/memory', {'memory_type': 'preferred_resource', 'key': key, 'value': value, **extra}, owner)


def apply(client, base, owner, ids):
    return client.post(base + '/context/apply', headers=owner, json={'memory_ids': ids})


def test_selected_persists_unselected_ignored_and_repeat_idempotent(client, base_plan):
    _, owner, base, resource, task = base_plan
    selected = memory(client, owner, {'task_name': task['name'], 'resource_id': resource['id']})
    other = post(client, base + '/tasks', {'name': 'Other', 'duration_minutes': 20}, owner)
    memory(client, owner, {'task_name': other['name'], 'resource_id': resource['id']}, key='Unselected')
    before = client.get(base + '/full', headers=owner).json()
    client.get(base + '/context', headers=owner)
    assert client.get(base + '/full', headers=owner).json() == before  # No silent reuse.
    first = apply(client, base, owner, [selected['id'], selected['id']])
    assert first.status_code == 200, first.text
    data = first.json()
    assert data['status'] == 'updated' and data['applied_memory_ids'] == [selected['id']]
    saved = client.get(base + '/full', headers=owner).json()
    assert saved['tasks'] == before['tasks'] and saved['resources'] == before['resources']
    assert len(saved['constraints']) == 1
    rule = saved['constraints'][0]
    assert rule['parameters'] == {'task_id': task['id'], 'resource_id': resource['id']}
    assert (rule['constraint_type'], rule['hardness'], rule['source'], rule['enabled']) == ('preferred_resource', 'soft', 'memory', True)
    assert data['created_constraint_ids'] == [rule['id']]
    repeated = apply(client, base, owner, [selected['id']]).json()
    assert repeated['status'] == 'unchanged' and repeated['created_constraint_ids'] == []
    assert repeated['reused_constraint_ids'] == [rule['id']]
    assert client.get(base + '/full', headers=owner).json() == saved
    assert apply(client, base, owner, []).json()['status'] == 'unchanged'
    assert client.get(base + '/full', headers=owner).json() == saved


def test_name_based_habit_and_equivalent_manual_rule_are_reused(client, base_plan):
    _, owner, base, resource, task = base_plan
    selected = memory(client, owner, {'task_name': task['name'], 'resource_name': resource['name']}, source='habit')
    rule = post(client, base + '/constraints', {'constraint_type': 'preferred_resource', 'hardness': 'soft', 'parameters': {'task_id': task['id'], 'resource_id': resource['id']}}, owner)
    result = apply(client, base, owner, [selected['id']])
    assert result.status_code == 200, result.text
    assert result.json()['reused_constraint_ids'] == [rule['id']]
    assert result.json()['created_constraint_ids'] == []
    assert result.json()['constraints'][0]['source'] == 'manual'


def test_foreign_plan_and_memory_are_blocked_atomically(client, base_plan, actors):
    _, owner, base, resource, task = base_plan
    own = memory(client, owner, {'task_name': task['name'], 'resource_id': resource['id']})
    foreign = memory(client, actors[1], {'task_name': task['name'], 'resource_id': resource['id']})
    before = client.get(base + '/full', headers=owner).json()
    assert apply(client, base, actors[1], [foreign['id']]).status_code == 404
    assert apply(client, base, owner, [own['id'], foreign['id']]).status_code == 404
    assert apply(client, base, owner, [own['id'], 99999]).status_code == 404
    assert client.get(base + '/full', headers=owner).json() == before


@pytest.mark.parametrize('state', ['disabled', 'inactive', 'unconfirmed'])
def test_consent_and_approval_required(client, base_plan, db_engine, state):
    _, owner, base, resource, task = base_plan
    selected = memory(client, owner, {'task_name': task['name'], 'resource_id': resource['id']})
    if state == 'disabled':
        client.put('/api/memory/consent', headers=owner, json={'enabled': False})
    else:
        with Session(db_engine) as db:
            record = db.get(PlanningMemory, selected['id'])
            setattr(record, 'active' if state == 'inactive' else 'confirmed', False)
            db.commit()
    before = client.get(base + '/full', headers=owner).json()
    assert apply(client, base, owner, [selected['id']]).status_code == 409
    assert client.get(base + '/full', headers=owner).json() == before


@pytest.mark.parametrize('value,kind', [
    ({'task_name': 'Missing', 'resource_id': 1}, 'preferred_resource'),
    ({'task_name': 'T1', 'resource_id': 99999}, 'preferred_resource'),
    ({'resource_name': 'Dev'}, 'preferred_resource'),
    ({'text': 'Morning'}, 'working_hours'),
])
def test_invalid_selection_never_partially_applies(client, base_plan, value, kind):
    _, owner, base, resource, task = base_plan
    good = memory(client, owner, {'task_name': task['name'], 'resource_id': resource['id']})
    bad = memory(client, owner, value, key='Invalid', memory_type=kind)
    before = client.get(base + '/full', headers=owner).json()
    result = apply(client, base, owner, [good['id'], bad['id']])
    assert result.status_code == 422, result.text
    assert client.get(base + '/full', headers=owner).json() == before
