import pytest

from behaviour.executor import compile_behaviours, run_step
from behaviour.base import BehaviourModule
from behaviour.registry import register_behaviour
from behaviour.model import SimulationModel
from topology.topology import build_topologies
from runner.soa import to_soa
from scheduler.scheduler import compile_scheduling

def test_compile_behaviours_success(sample_soa):
    config = {'behaviour': {'person': [{'expression': 'state["energy"] += 1', 'topology_name': 'sample_network'}]}, 'topologies': {'sample_network': {'mode': 'all_pairs', 'agent_types': ['person'], 'allow_self_interaction': True}}}
    pairs = build_topologies(config, sample_soa)

    compiled = compile_behaviours(config, pairs)

    assert len(compiled) == 1

def test_compile_behaviours_no_topologies_throws_value_error(sample_soa):
    config = {'behaviour': {'person': [{'expression': 'state["energy"] += 1', 'topology_name': 'sample_network_01'}]}, 'topologies': {'sample_network': {'mode': 'all_pairs', 'agent_types': ['person'], 'allow_self_interaction': True}}}
    pairs = build_topologies(config, sample_soa)

    with pytest.raises(ValueError) as e:
        compile_behaviours(config, pairs)
    assert e.match("unknown topology ")

def test_compile_behaviours_no_behaviour_settings_throws_value_error(sample_soa):
    config = {'topologies': {
        'sample_network': {'mode': 'all_pairs', 'agent_types': ['person'], 'allow_self_interaction': True}}}
    pairs = build_topologies(config, sample_soa)

    with pytest.raises(ValueError) as e:
        compile_behaviours(config, pairs)
    assert str(e.value) == "Config must contain a 'behaviour' section with at least one agent type's behaviour sequence defined."

def test_compile_behaviours_behaviour_settings_invalid_agent_throws_value_error(sample_soa):
    config = {'behaviour': {}, 'topologies': {
        'sample_network': {'mode': 'all_pairs', 'agent_types': ['person'], 'allow_self_interaction': True}}}
    pairs = build_topologies(config, sample_soa)

    with pytest.raises(ValueError) as e:
        compile_behaviours(config, pairs)
    assert str(e.value) == "Config must contain a 'behaviour' section with at least one agent type's behaviour sequence defined."

def test_compile_behaviours_behaviour_settings_without_expression_module_throws_value_error(sample_soa):
    config = {'behaviour': {'person': [{'expr': 'state["energy"] += 1'}]}, 'topologies': {
        'sample_network': {'mode': 'all_pairs', 'agent_types': ['person'], 'allow_self_interaction': True}}}
    pairs = build_topologies(config, sample_soa)

    with pytest.raises(ValueError) as e:
        compile_behaviours(config, pairs)
    assert e.match("behaviour entry must contain ")

def test_run_step_expr_success(sample_agents_dict, person_agent_types):
    config = {'behaviour': {'person': [{'expression': 'state["energy"] = 1', 'topology_name': 'sample_network'}]},
              'topologies': {
                  'sample_network': {'mode': 'all_pairs', 'agent_types': ['person'], 'allow_self_interaction': True}}, 'scheduling': {'order': 'all_at_once', 'read_mode': 'frozen'}}
    pairs = build_topologies(config, to_soa([agent_state for agent_id, agent_state in sample_agents_dict.items()]))
    compiled = compile_behaviours(config, pairs)
    model = SimulationModel()
    schedule_config = compile_scheduling(config)

    run_step(sample_agents_dict, compiled, pairs, model, schedule_config, person_agent_types,1)

    for agents in sample_agents_dict.values():
        assert agents.state['energy'] == 1

def test_run_step_module_success(sample_agents_dict, person_agent_types):
    @register_behaviour("testModule01")
    class Module01(BehaviourModule):
        def apply(self, agent, neighbours, accessor, model):
            agent.set("energy", 2)

    config = {'behaviour': {'person': [{'module': 'testModule01', 'write_mode': 'deferred', 'topology_name': 'sample_network'}]},
              'topologies': {
                  'sample_network': {'mode': 'all_pairs', 'agent_types': ['person'], 'allow_self_interaction': True}}, 'scheduling': {'order': 'all_at_once', 'read_mode': 'frozen'}}
    pairs = build_topologies(config, to_soa([agent_state for agent_id, agent_state in sample_agents_dict.items()]))
    compiled = compile_behaviours(config, pairs)
    model = SimulationModel()
    schedule_config = compile_scheduling(config)

    run_step(sample_agents_dict, compiled, pairs, model, schedule_config, person_agent_types,1)

    for agents in sample_agents_dict.values():
        assert agents.state['energy'] == 2

def test_run_step_self_write_visible_to_next_entry(sample_agents_dict, person_agent_types):
    @register_behaviour("testIncrement")
    class IncrementModule(BehaviourModule):
        def apply(self, agent, neighbours, accessor, model):
            agent.set("energy", agent.get("energy") + 1)

    config = {'behaviour': {'person': [
        {'module': 'testIncrement', 'write_mode': 'deferred'},
        {'expression': 'state["energy"] += 10'},
    ]}, 'topologies': {
        'sample_network': {'mode': 'all_pairs', 'agent_types': ['person'], 'allow_self_interaction': True}}, 'scheduling': {'order': 'all_at_once', 'read_mode': 'frozen'}}
    pairs = build_topologies(config, to_soa(list(sample_agents_dict.values())))
    compiled = compile_behaviours(config, pairs)
    model = SimulationModel()
    schedule_config = compile_scheduling(config)

    agent = list(sample_agents_dict.values())[0]
    agent.state["energy"] = 5

    run_step({agent.agent_id: agent}, compiled, pairs, model, schedule_config, person_agent_types,1)

    # If the expression saw the module's +1 first, result is (5+1)+10 = 16.
    # If it only saw the original value, result would be 5+10 = 15 (wrong).
    assert agent.state["energy"] == 16

def test_run_step_immediate_neighbour_write_applies_within_step(sample_agents_dict, person_agent_types):
    @register_behaviour("testKill")
    class KillModule(BehaviourModule):
        def apply(self, agent, neighbours, accessor, model):
            for n in neighbours:
                accessor.write(n, "energy", 0)

    config = {'behaviour': {'person': [
        {'module': 'testKill', 'write_mode': 'immediate', 'topology_name': 'sample_network'}
    ]}, 'topologies': {
        'sample_network': {'mode': 'all_pairs', 'agent_types': ['person'], 'allow_self_interaction': True}}, 'scheduling': {'order': 'all_at_once', 'read_mode': 'frozen'}}
    pairs = build_topologies(config, to_soa(list(sample_agents_dict.values())))
    compiled = compile_behaviours(config, pairs)
    model = SimulationModel()
    schedule_config = compile_scheduling(config)

    run_step(sample_agents_dict, compiled, pairs, model, schedule_config, person_agent_types,1)

    for agent in sample_agents_dict.values():
        assert agent.state["energy"] == 0

def test_run_step_module_with_params_success(sample_agents_dict, person_agent_types):
    @register_behaviour("testIncrementByAmount")
    class IncrementByAmountModule(BehaviourModule):
        def __init__(self, amount):
            self.amount = amount

        def apply(self, agent, neighbours, accessor, model):
            agent.set("energy", agent.get("energy") + self.amount)

    config = {'behaviour': {'person': [
        {'module': 'testIncrementByAmount', 'write_mode': 'deferred', 'params': {'amount': 7}}
    ]}, 'topologies': {
        'sample_network': {'mode': 'all_pairs', 'agent_types': ['person'], 'allow_self_interaction': True}}, 'scheduling': {'order': 'all_at_once', 'read_mode': 'frozen'}}
    pairs = build_topologies(config, to_soa(list(sample_agents_dict.values())))
    compiled = compile_behaviours(config, pairs)
    model = SimulationModel()
    schedule_config = compile_scheduling(config)

    agent = list(sample_agents_dict.values())[0]
    agent.state["energy"] = 10

    run_step({agent.agent_id: agent}, compiled, pairs, model, schedule_config, person_agent_types,1)

    assert agent.state["energy"] == 17  # 10 + 7

def test_run_step_reproduce_applies_after_step(sample_agents_dict, person_agent_types):
    @register_behaviour("testReproduce")
    class ReproduceModule(BehaviourModule):
        def apply(self, agent, neighbours, accessor, model):
            model.reproduce(agent_type=agent.agent_type_name, parent_id=agent.agent_id)

    config = {
        'behaviour': {'person': [
            {'module': 'testReproduce', 'write_mode': 'immediate', 'topology_name': 'sample_network'}
        ]},
        'topologies': {'sample_network': {'mode': 'all_pairs', 'agent_types': ['person'], 'allow_self_interaction': True}},
        'scheduling': {'order': 'all_at_once', 'read_mode': 'frozen'}
    }
    pairs = build_topologies(config, to_soa(list(sample_agents_dict.values())))
    compiled = compile_behaviours(config, pairs)
    model = SimulationModel()
    schedule_config = compile_scheduling(config)

    original_count = len(sample_agents_dict)

    run_step(sample_agents_dict, compiled, pairs, model, schedule_config, person_agent_types, 1)

    # Every agent reproduced once this step -> population should double.
    assert len(sample_agents_dict) == original_count * 2


def test_run_step_remove_applies_after_step(sample_agents_dict, person_agent_types):
    @register_behaviour("testRemove")
    class RemoveModule(BehaviourModule):
        def apply(self, agent, neighbours, accessor, model):
            model.remove(agent.agent_id)

    config = {
        'behaviour': {'person': [
            {'module': 'testRemove', 'write_mode': 'immediate', 'topology_name': 'sample_network'}
        ]},
        'topologies': {'sample_network': {'mode': 'all_pairs', 'agent_types': ['person'], 'allow_self_interaction': True}},
        'scheduling': {'order': 'all_at_once', 'read_mode': 'frozen'}
    }
    pairs = build_topologies(config, to_soa(list(sample_agents_dict.values())))
    compiled = compile_behaviours(config, pairs)
    model = SimulationModel()
    schedule_config = compile_scheduling(config)

    run_step(sample_agents_dict, compiled, pairs, model, schedule_config, person_agent_types, 1)

    assert len(sample_agents_dict) == 0


def test_run_step_external_entry_applies_after_step(sample_agents_dict, person_agent_types):
    original_count = len(sample_agents_dict)

    @register_behaviour("testExternalEntry")
    class ExternalEntryModule(BehaviourModule):
        def apply(self, agent, neighbours, accessor, model):
            model.external_entry(agent_type=agent.agent_type_name, count=2)

    config = {
        'behaviour': {'person': [
            {'module': 'testExternalEntry', 'write_mode': 'immediate', 'topology_name': 'sample_network'}
        ]},
        'topologies': {'sample_network': {'mode': 'all_pairs', 'agent_types': ['person'], 'allow_self_interaction': True}},
        'scheduling': {'order': 'all_at_once', 'read_mode': 'frozen'}
    }
    pairs = build_topologies(config, to_soa(list(sample_agents_dict.values())))
    compiled = compile_behaviours(config, pairs)
    model = SimulationModel()
    schedule_config = compile_scheduling(config)

    run_step(sample_agents_dict, compiled, pairs, model, schedule_config, person_agent_types, 1)

    # Every original agent triggers +2 new agents this step.
    assert len(sample_agents_dict) == original_count * 3


def test_run_step_pending_events_do_not_leak_into_next_step(sample_agents_dict, person_agent_types):
    """Proves _reset_for_step actually clears _pending_events — a module
    firing once should not have its event silently re-applied on a
    later step."""
    call_count = {"n": 0}

    @register_behaviour("testRemoveOnce")
    class RemoveOnceModule(BehaviourModule):
        def apply(self, agent, neighbours, accessor, model):
            call_count["n"] += 1
            if call_count["n"] == 1:
                model.remove(agent.agent_id)

    config = {
        'behaviour': {'person': [
            {'module': 'testRemoveOnce', 'write_mode': 'immediate', 'topology_name': 'sample_network'}
        ]},
        'topologies': {'sample_network': {'mode': 'all_pairs', 'agent_types': ['person'], 'allow_self_interaction': True}},
        'scheduling': {'order': 'all_at_once', 'read_mode': 'frozen'}
    }
    pairs = build_topologies(config, to_soa(list(sample_agents_dict.values())))
    compiled = compile_behaviours(config, pairs)
    model = SimulationModel()
    schedule_config = compile_scheduling(config)

    original_count = len(sample_agents_dict)

    run_step(sample_agents_dict, compiled, pairs, model, schedule_config, person_agent_types, 1)
    assert len(sample_agents_dict) == original_count - 1

    count_after_step_1 = len(sample_agents_dict)
    run_step(sample_agents_dict, compiled, pairs, model, schedule_config, person_agent_types, 2)

    # Step 2's surviving agents don't call model.remove again (call_count > 1
    # branch does nothing) -> population must be unchanged, proving no
    # leftover event from step 1 re-applied.
    assert len(sample_agents_dict) == count_after_step_1