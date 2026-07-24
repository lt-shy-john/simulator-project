import pytest
import random

from scheduler.scheduler import compile_scheduling, resolve_step_agents, consume_lifetime_action

def test_scheduler_all_success():
    config = {'scheduling': {'order': 'all_at_once', 'read_mode': 'frozen'}}

    schedule_config = compile_scheduling(config)
    assert schedule_config.order == 'all_at_once'

def test_scheduler_random_order_success():
    config = {'scheduling': {'order': 'random', 'read_mode': 'live'}}

    schedule_config = compile_scheduling(config)
    assert schedule_config.order == 'random'

def test_scheduler_priority_all_population_success():
    config = {'scheduling': {'order': 'priority', 'read_mode': 'live', 'priority_attribute': 'energy', 'quota': {'mode': 'lifetime_budget', 'limit': 3, 'scope': 'person'}}}

    schedule_config = compile_scheduling(config)
    assert schedule_config.order == 'priority'
    assert schedule_config.quota.scope == 'person'

def test_scheduler_priority_per_agent_success():
    config = {'scheduling': {'order': 'priority', 'read_mode': 'live', 'priority_attribute': 'energy', 'quota': {'mode': 'step_random_subset', 'limit': 3, 'scope': 'person'}}}

    schedule_config = compile_scheduling(config)
    assert schedule_config.order == 'priority'
    assert schedule_config.quota.scope == 'person'

def test_resolve_step_agents_all_success(sample_agents_with_action_quota_dict):
    config = {'scheduling': {'order': 'all_at_once', 'read_mode': 'frozen'}}
    schedule_config = compile_scheduling(config)

    schedule_result = resolve_step_agents(schedule_config, sample_agents_with_action_quota_dict)

    assert len(schedule_result) == len(sample_agents_with_action_quota_dict)

def test_resolve_step_agents_random_order_success(sample_agents_with_action_quota_dict):
    config = {'scheduling': {'order': 'random', 'read_mode': 'live'}}
    schedule_config = compile_scheduling(config)

    schedule_result = resolve_step_agents(schedule_config, sample_agents_with_action_quota_dict)

    assert len(schedule_result) == len(sample_agents_with_action_quota_dict)
    assert set(schedule_result) == set(sample_agents_with_action_quota_dict.keys())

def test_resolve_step_agents_priority_mode_success(sample_agents_with_action_quota_dict):
    config = {'scheduling': {'order': 'priority', 'read_mode': 'live', 'priority_attribute': 'energy',
                             'quota': {'mode': 'lifetime_budget', 'limit': 3, 'scope': 'person'}}}
    schedule_config = compile_scheduling(config)

    target_agent = list(sample_agents_with_action_quota_dict.values())[0]
    target_agent.state['actions_remaining'] = 1  # one action left

    # Should be eligible this step (budget = 1)
    result_before = resolve_step_agents(schedule_config, sample_agents_with_action_quota_dict)
    assert target_agent.agent_id in result_before

    # Simulate the agent actually acting and its budget being consumed
    consume_lifetime_action(schedule_config, target_agent)
    assert target_agent.state['actions_remaining'] == 0

    # Now should be ineligible on the next resolution
    result_after = resolve_step_agents(schedule_config, sample_agents_with_action_quota_dict)
    assert target_agent.agent_id not in result_after

def test_resolve_step_agents_step_random_subset_caps_at_limit(sample_agents_with_action_quota_dict):
    config = {'scheduling': {'order': 'all_at_once', 'read_mode': 'frozen',
                             'quota': {'mode': 'step_random_subset', 'limit': 3, 'scope': 'person'}}}
    schedule_config = compile_scheduling(config)

    schedule_result = resolve_step_agents(schedule_config, sample_agents_with_action_quota_dict)

    assert len(schedule_result) == 3

def test_consume_lifetime_action_success(sample_agents_with_action_quota_dict):
    config = {'scheduling': {'order': 'priority', 'read_mode': 'live', 'priority_attribute': 'energy', 'quota': {'mode': 'lifetime_budget', 'limit': 3, 'scope': 'person'}}}
    sample_agent = random.choice(list(sample_agents_with_action_quota_dict.values()))
    schedule_config = compile_scheduling(config)
    schedule_result = resolve_step_agents(schedule_config, sample_agents_with_action_quota_dict)

    consume_lifetime_action(schedule_config, sample_agent)

    assert sample_agent.get("actions_remaining") == 2

    consume_lifetime_action(schedule_config, sample_agent)

    assert sample_agent.get("actions_remaining") == 1