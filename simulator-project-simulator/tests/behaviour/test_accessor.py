import pytest
import uuid
import random

from behaviour.accessor import NeighbourAccessor, apply_deferred_writes

def test_read_neighbour_id_success(sample_agents_dict):
    neighbour_accessor = NeighbourAccessor(sample_agents_dict, sample_agents_dict, None, "immediate")

    target_agent_id = random.sample(list(sample_agents_dict), 1)[0]
    result = neighbour_accessor.read(target_agent_id, 'energy')

    assert result == sample_agents_dict[target_agent_id].state['energy']

def test_read_neighbour_id_inexistent_throws_key_error(sample_agents_dict):
    neighbour_accessor = NeighbourAccessor(sample_agents_dict, sample_agents_dict, None, "immediate")

    target_agent_id = str(uuid.uuid4())
    with pytest.raises(KeyError):
        neighbour_accessor.read(target_agent_id, 'energy')

def test_read_undefined_attribute_key_throws_key_error(sample_agents_dict):
    neighbour_accessor = NeighbourAccessor(sample_agents_dict, sample_agents_dict, None, "immediate")

    target_agent_id = random.sample(list(sample_agents_dict), 1)[0]
    with pytest.raises(KeyError):
        neighbour_accessor.read(target_agent_id, 'energy01')

def test_immediate_write_neighbour_id_success(sample_agents_dict):
    neighbour_accessor = NeighbourAccessor(sample_agents_dict, sample_agents_dict, None, "immediate")
    target_agent_id = random.sample(list(sample_agents_dict), 1)[0]

    neighbour_accessor.write(target_agent_id, 'energy', 10)

    assert sample_agents_dict[target_agent_id].state['energy'] == 10

def test_deferred_write_neighbour_id_success(sample_agents_dict):
    deferred_writes = []
    neighbour_accessor = NeighbourAccessor(sample_agents_dict, sample_agents_dict, deferred_writes, "deferred")
    target_agent_id = random.sample(list(sample_agents_dict), 1)[0]
    original_energy = sample_agents_dict[target_agent_id].state['energy']

    neighbour_accessor.write(target_agent_id, 'energy', 10)

    assert sample_agents_dict[target_agent_id].state['energy'] == original_energy  # unchanged
    assert (target_agent_id, 'energy', 10) in deferred_writes  # but queued

def test_deferred_write_does_not_apply_immediately(sample_agents_dict):
    deferred_writes = []
    neighbour_accessor = NeighbourAccessor(sample_agents_dict, sample_agents_dict, deferred_writes, "deferred")
    target_agent_id = random.sample(list(sample_agents_dict), 1)[0]

    neighbour_accessor.write(target_agent_id, 'energy', 100)

    assert sample_agents_dict[target_agent_id].state['energy'] != 100
    assert (target_agent_id, 'energy', 100) in deferred_writes

def test_apply_deferred_writes_last_write_wins(sample_agents_dict):
    deferred_writes = []
    neighbour_accessor = NeighbourAccessor(sample_agents_dict, sample_agents_dict, deferred_writes, "deferred")
    target_agent_id = random.sample(list(sample_agents_dict), 1)[0]

    neighbour_accessor.write(target_agent_id, 'energy', 10)
    neighbour_accessor.write(target_agent_id, 'energy', 20)

    apply_deferred_writes(sample_agents_dict, deferred_writes)

    assert sample_agents_dict[target_agent_id].state['energy'] == 20

def test_apply_deferred_writes_empty_queue_is_noop(sample_agents_dict):
    original_state = {aid: dict(agent.state) for aid, agent in sample_agents_dict.items()}
    apply_deferred_writes(sample_agents_dict, [])
    for aid, agent in sample_agents_dict.items():
        assert agent.state == original_state[aid]

def test_immediate_write_neighbour_id_inexistent_throws_key_error(sample_agents_dict):
    neighbour_accessor = NeighbourAccessor(sample_agents_dict, sample_agents_dict, None, "immediate")
    target_agent_id = str(uuid.uuid4())
    with pytest.raises(KeyError):
        neighbour_accessor.write(target_agent_id, 'energy', 1)

def test_apply_deferred_write_neighbour_id_success(sample_agents_dict):
    deferred_writes = []
    neighbour_accessor = NeighbourAccessor(sample_agents_dict, sample_agents_dict, deferred_writes, "deferred")
    target_agent_id = random.sample(list(sample_agents_dict), 1)[0]
    neighbour_accessor.write(target_agent_id, 'energy', 10)

    apply_deferred_writes(sample_agents_dict, deferred_writes)

    assert sample_agents_dict[target_agent_id].state['energy'] == 10

def test_apply_deferred_write_neighbour_id_inexistent_throws_key_error(sample_agents_dict):
    deferred_writes = []
    neighbour_accessor = NeighbourAccessor(sample_agents_dict, sample_agents_dict, deferred_writes, "deferred")
    target_agent_id = str(uuid.uuid4())
    neighbour_accessor.write(target_agent_id, 'energy', 10)

    with pytest.raises(KeyError) as e:
        apply_deferred_writes(sample_agents_dict, deferred_writes)
    assert e.match(f"Cannot apply deferred write: neighbour_id '{target_agent_id}'")