import numpy as np
import pytest

from behaviour.base import BehaviourModule
from behaviour.executor import run_step
from behaviour.registry import register_behaviour
from behaviour.executor import compile_behaviours
from behaviour.model import SimulationModel
from lifecycle.lifecycle import (
    ReproduceEvent,
    ExternalEntryEvent,
    RemoveEvent,
    apply_pending_lifecycle_events,
)
from scheduler.scheduler import compile_scheduling
from topology.topology import build_topologies
from runner.soa import to_soa


# Same topology/config shape used across S-07/S-08/S-10 tests: build_topologies
# requires a non-empty topologies config even when neighbours aren't used.
def _base_config(module_name: str | None = None):
    config = {
        "topologies": {
            "sample_network": {
                "mode": "all_pairs",
                "agent_types": ["person"],
                "allow_self_interaction": True,
            }
        },
        "scheduling": {"order": "all_at_once", "read_mode": "frozen"},
    }
    if module_name is not None:
        config["behaviour"] = {
            "person": [
                {
                    "module": module_name,
                    "write_mode": "deferred",
                    "topology_name": "sample_network",
                }
            ]
        }
    else:
        config["behaviour"] = {}
    return config


def _run_one_step(sample_agents_dict, person_agent_types, module_name=None):
    """Builds the full pipeline (topologies/compiled behaviours/model/schedule)
    and runs a single step, returning the model used."""
    config = _base_config(module_name)
    soa = to_soa([agent for agent in sample_agents_dict.values()])
    pairs = build_topologies(config, soa)
    compiled = compile_behaviours(config, pairs)
    model = SimulationModel()
    schedule_config = compile_scheduling(config)

    run_step(sample_agents_dict, compiled, pairs, model, schedule_config, person_agent_types, 1)
    return model


def test_agent_reproduced_logged(sample_single_agent_dict, person_agent_types):
    parent = list(sample_single_agent_dict.values())[0]
    event = [ReproduceEvent(agent_type=parent.agent_type_name, parent_id=parent.agent_id)]

    result = apply_pending_lifecycle_events(
        sample_single_agent_dict, event, person_agent_types, np.random.default_rng(0)
    )

    assert len(result) == 1
    event_type, agent_id, data = result[0]
    assert event_type == "agent_created"
    assert data["via"] == "reproduction"
    assert data["parent_id"] == parent.agent_id


def test_agent_externally_introduced_logged(sample_single_agent_dict, person_agent_types):
    parent = list(sample_single_agent_dict.values())[0]
    event = [ExternalEntryEvent(agent_type=parent.agent_type_name, count=3)]

    result = apply_pending_lifecycle_events(
        sample_single_agent_dict, event, person_agent_types, np.random.default_rng(0)
    )

    assert len(result) == 1  # one batch event, not 3
    record = result[0]
    assert record["event_type"] == "agent_created"
    assert record["data"]["via"] == "external_entry"
    assert record["data"]["count"] == 3
    assert len(record["data"]["agent_ids"]) == 3

def test_agent_removed_logged(sample_single_agent_dict, person_agent_types):
    parent = list(sample_single_agent_dict.values())[0]
    event = [RemoveEvent(agent_id=parent.agent_id)]

    result = apply_pending_lifecycle_events(
        sample_single_agent_dict, event, person_agent_types, np.random.default_rng(0)
    )

    assert len(result) == 1
    event_type, agent_id, data = result[0]
    assert event_type == "agent_removed"
    assert agent_id == parent.agent_id


def test_step_started_logged(sample_agents_dict, person_agent_types):
    # step_start/step_end fire from run_step itself, not from
    # apply_pending_lifecycle_events - needs the full pipeline.
    model = _run_one_step(sample_agents_dict, person_agent_types)

    events = model.get_events(event_types=["step_start"])
    assert len(events) == 1
    assert events[0]["step"] == 1


def test_step_ended_logged(sample_agents_dict, person_agent_types):
    model = _run_one_step(sample_agents_dict, person_agent_types)

    events = model.get_events(event_types=["step_end"])
    assert len(events) == 1
    assert events[0]["step"] == 1


def test_behaviour_module_logged(sample_agents_dict, person_agent_types):
    @register_behaviour("testModuleEventLog")
    class LoggingModule(BehaviourModule):
        def apply(self, agent, neighbours, accessor, model):
            model.log_event("custom_event", agent_id=agent.agent_id, data={"foo": "bar"})

    model = _run_one_step(sample_agents_dict, person_agent_types, module_name="testModuleEventLog")

    events = model.get_events(event_types=["custom_event"])
    assert any(e["data"] == {"foo": "bar"} for e in events)


def test_filter_log_single_type(sample_agents_dict, person_agent_types):
    @register_behaviour("testModuleEventLogFilter")
    class LoggingModule(BehaviourModule):
        def apply(self, agent, neighbours, accessor, model):
            model.log_event("custom_event", agent_id=agent.agent_id, data={})

    model = _run_one_step(sample_agents_dict, person_agent_types, module_name="testModuleEventLogFilter")

    all_events = model.get_events()
    assert len(all_events) > 1  # step_start/step_end + at least one custom_event

    filtered = model.get_events(event_types=["step_start"])
    assert all(e["event_type"] == "step_start" for e in filtered)
    assert len(filtered) == 1  # exactly one step_start for one step


def test_filter_log_multiple_types(sample_agents_dict, person_agent_types):
    @register_behaviour("testModuleEventLogFilterMulti")
    class LoggingModule(BehaviourModule):
        def apply(self, agent, neighbours, accessor, model):
            model.log_event("custom_event", agent_id=agent.agent_id, data={})

    model = _run_one_step(sample_agents_dict, person_agent_types, module_name="testModuleEventLogFilterMulti")

    all_events = model.get_events()
    filtered = model.get_events(event_types=["step_start", "step_end"])

    assert all(e["event_type"] in {"step_start", "step_end"} for e in filtered)
    # union, not intersection: exactly the matching subset of all_events, nothing extra/missing
    expected_count = sum(1 for e in all_events if e["event_type"] in {"step_start", "step_end"})
    assert len(filtered) == expected_count

def test_event_log_separate_from_agent_data(sample_single_agent_dict):
    model = SimulationModel()
    model._reset_for_step(1, sample_single_agent_dict)
    model.log_event("step_start", agent_id=None, data={})

    events = model.get_events()
    assert len(events) == 1
    assert all(isinstance(e, dict) and "event_type" in e for e in events)

    # agent-level data (model.agents) is untouched by logging - no event
    # fields leak into agent state, and events aren't stored alongside it
    assert all(not hasattr(a, "event_type") for a in model.agents)
    assert events not in (model.agents,)  # distinct storage, not aliased