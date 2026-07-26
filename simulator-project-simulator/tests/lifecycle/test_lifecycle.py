import pytest

from lifecycle.lifecycle import apply_pending_lifecycle_events, ReproduceEvent, ExternalEntryEvent, RemoveEvent


def test_apply_pending_lifecycle_events_reproduce_success(sample_single_agent_dict, person_agent_types):
    event = [ReproduceEvent(agent_type=list(sample_single_agent_dict.values())[0].agent_type_name, parent_id=list(sample_single_agent_dict.values())[0].agent_id)]
    apply_pending_lifecycle_events(sample_single_agent_dict, event, person_agent_types)

    assert (len(sample_single_agent_dict) == 2)

def test_apply_pending_lifecycle_events_birth_success(sample_single_agent_dict, person_agent_types):
    event = [ExternalEntryEvent(agent_type=list(sample_single_agent_dict.values())[0].agent_type_name, count=1)]
    apply_pending_lifecycle_events(sample_single_agent_dict, event, person_agent_types)

    assert (len(sample_single_agent_dict) == 2)

def test_apply_pending_lifecycle_events_removal_success(sample_single_agent_dict, person_agent_types):
    event = [RemoveEvent(agent_id=list(sample_single_agent_dict.values())[0].agent_id)]
    apply_pending_lifecycle_events(sample_single_agent_dict, event, person_agent_types)

    assert(len(sample_single_agent_dict) == 0)

def test_apply_pending_lifecycle_events_unknown_throws_value_error(sample_single_agent_dict, person_agent_types):
    class UnknownEvent:
        pass
    event = [UnknownEvent()]
    with pytest.raises(ValueError) as e:
        apply_pending_lifecycle_events(sample_single_agent_dict, event, person_agent_types)