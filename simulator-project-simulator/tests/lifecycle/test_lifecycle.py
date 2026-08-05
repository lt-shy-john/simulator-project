import pytest
import uuid
import numpy as np
import lifecycle.lifecycle as lifecycle_module

from lifecycle.lifecycle import apply_pending_lifecycle_events, ReproduceEvent, ExternalEntryEvent, RemoveEvent

def test_apply_pending_lifecycle_events_reproduce_success(sample_single_agent_dict, person_agent_types):
    event = [ReproduceEvent(agent_type=list(sample_single_agent_dict.values())[0].agent_type_name, parent_id=list(sample_single_agent_dict.values())[0].agent_id)]
    apply_pending_lifecycle_events(sample_single_agent_dict, event, person_agent_types)

    assert (len(sample_single_agent_dict) == 2)

def test_apply_pending_lifecycle_events_reproduce_fresh_attribute_success(sample_single_agent_dict, person_agent_types, monkeypatch):
    parent = list(sample_single_agent_dict.values())[0]
    parent_energy = parent.state['energy']
    fixed_value = np.array([parent_energy + 1])

    monkeypatch.setattr(
        lifecycle_module,
        "_sample_distribution",
        lambda attr, count=1: (print("MOCK HIT"), fixed_value)[1]
    )

    event = [ReproduceEvent(
        agent_type=parent.agent_type_name,
        parent_id=parent.agent_id,
        fresh_attributes=['energy']
    )]

    apply_pending_lifecycle_events(sample_single_agent_dict, event, person_agent_types)

    agent_ids_ls = list(sample_single_agent_dict.keys())
    assert (len(agent_ids_ls) == 2)

    child = sample_single_agent_dict[agent_ids_ls[1]]
    assert child.state['energy'] == parent_energy + 1  # exact, deterministic
    assert sample_single_agent_dict[agent_ids_ls[0]].state['energy'] == parent_energy  # parent untouched

def test_apply_pending_lifecycle_events_birth_success(sample_single_agent_dict, person_agent_types):
    event = [ExternalEntryEvent(agent_type=list(sample_single_agent_dict.values())[0].agent_type_name, count=1)]
    apply_pending_lifecycle_events(sample_single_agent_dict, event, person_agent_types)

    assert (len(sample_single_agent_dict) == 2)

def test_apply_pending_lifecycle_events_removal_success(sample_single_agent_dict, person_agent_types):
    event = [RemoveEvent(agent_id=list(sample_single_agent_dict.values())[0].agent_id)]
    apply_pending_lifecycle_events(sample_single_agent_dict, event, person_agent_types)

    assert(len(sample_single_agent_dict) == 0)

def test_apply_remove_already_removed_agent_is_noop(sample_single_agent_dict, person_agent_types):
    event = [RemoveEvent(agent_id=list(sample_single_agent_dict.values())[0].agent_id)]
    apply_pending_lifecycle_events(sample_single_agent_dict, event, person_agent_types)
    apply_pending_lifecycle_events(sample_single_agent_dict, event, person_agent_types)

    assert (len(sample_single_agent_dict) == 0)

def test_reproduce_and_external_entry_generate_unique_ids(sample_single_agent_dict, person_agent_types):
    event = [ReproduceEvent(agent_type=list(sample_single_agent_dict.values())[0].agent_type_name, parent_id=list(sample_single_agent_dict.values())[0].agent_id), ReproduceEvent(agent_type=list(sample_single_agent_dict.values())[0].agent_type_name, parent_id=list(sample_single_agent_dict.values())[0].agent_id), ExternalEntryEvent(agent_type=list(sample_single_agent_dict.values())[0].agent_type_name, count=1)]
    apply_pending_lifecycle_events(sample_single_agent_dict, event, person_agent_types)
    assert (len(sample_single_agent_dict) == 4)

def test_apply_pending_lifecycle_events_external_entry_batch(sample_single_agent_dict, person_agent_types):
    event = [ExternalEntryEvent(agent_type=list(sample_single_agent_dict.values())[0].agent_type_name, count=3)]
    apply_pending_lifecycle_events(sample_single_agent_dict, event, person_agent_types)

    assert len(sample_single_agent_dict) == 4  # 1 original + 3 new
    # sanity: all new agents got distinct IDs
    assert len(set(sample_single_agent_dict.keys())) == 4

def test_apply_pending_lifecycle_events_unknown_throws_value_error(sample_single_agent_dict, person_agent_types):
    class UnknownEvent:
        pass
    event = [UnknownEvent()]
    with pytest.raises(ValueError) as e:
        apply_pending_lifecycle_events(sample_single_agent_dict, event, person_agent_types)

def test_apply_reproduce_unknown_parent_raises_key_error(sample_single_agent_dict, person_agent_types):
    event = [ReproduceEvent(agent_type=list(sample_single_agent_dict.values())[0].agent_type_name, parent_id=str(uuid.uuid4()))]
    with pytest.raises(KeyError) as e:
        apply_pending_lifecycle_events(sample_single_agent_dict, event, person_agent_types)
    assert e.match('Cannot reproduce: parent_id ')

def test_apply_reproduce_unknown_agent_type_raises_key_error(sample_single_agent_dict, person_agent_types):
    event = [ReproduceEvent(agent_type='???',
                            parent_id=list(sample_single_agent_dict.values())[0].agent_id, fresh_attributes=['energy'])]
    with pytest.raises(KeyError) as e:
        apply_pending_lifecycle_events(sample_single_agent_dict, event, person_agent_types)
    assert e.match('Cannot reproduce: agent_type ')

def test_apply_external_entry_unknown_agent_type_raises_key_error(sample_single_agent_dict, person_agent_types):
    event = [ExternalEntryEvent(agent_type='???', count=1)]
    with pytest.raises(KeyError) as e:
        apply_pending_lifecycle_events(sample_single_agent_dict, event, person_agent_types)
    assert e.match('Cannot process external entry: agent_type ')