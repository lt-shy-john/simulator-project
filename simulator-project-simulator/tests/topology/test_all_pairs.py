import pytest
import random

from topology.all_pairs import AllPairsTopology

def test_generate_all_pairs_invalid_agent_type(sample_soa):
    config = {'topologies': {'sample_network': {'mode': 'all_pairs', 'agent_types': ['invalid_agent_type']}}}
    with pytest.raises(ValueError):
        AllPairsTopology.from_config(config['topologies']['sample_network'], sample_soa)

def test_all_pairs_get_neighbours_success(sample_soa):
    config = {'topologies': {'sample_network': {'mode': 'all_pairs', 'agent_types': ['person']}}}
    pairs = AllPairsTopology.from_config(config['topologies']['sample_network'], sample_soa)

    # Pick a real agent ID from the population
    agent_ids = list(sample_soa['person']['__ids__'])
    focal_agent_id = str(agent_ids[0])

    neighbours = pairs.get_neighbours(focal_agent_id, sample_soa)

    assert len(neighbours) == len(agent_ids) - 1  # N-1, self excluded

def test_all_pairs_excludes_self_by_default(sample_soa):
    config = {'topologies': {'sample_network': {'mode': 'all_pairs', 'agent_types': ['person']}}}
    pairs = AllPairsTopology.from_config(config['topologies']['sample_network'], sample_soa)

    # Pick a real agent ID from the population
    agent_ids = list(sample_soa['person']['__ids__'])
    target_agent_id = str(agent_ids[random.randint(0, len(agent_ids) - 1)])

    neighbours = pairs.get_neighbours(target_agent_id, sample_soa)
    assert target_agent_id not in neighbours

    assert len(neighbours) == len(agent_ids) - 1  # N-1, self excluded

def test_all_pairs_allows_self_interaction_when_enabled(sample_soa):
    config = {'topologies': {'sample_network': {'mode': 'all_pairs', 'agent_types': ['person'], 'allow_self_interaction': True}}}
    pairs = AllPairsTopology.from_config(config['topologies']['sample_network'], sample_soa)

    # Pick a real agent ID from the population
    agent_ids = list(sample_soa['person']['__ids__'])
    target_agent_id = str(agent_ids[random.randint(0, len(agent_ids) - 1)])

    neighbours = pairs.get_neighbours(target_agent_id, sample_soa)
    assert target_agent_id in neighbours
    assert len(neighbours) == len(agent_ids)

def test_all_pairs_cross_type_interaction_success(mixed_type_soa):
    config = {'topologies': {
        'sample_network': {'mode': 'all_pairs', 'agent_types': ['predator', 'prey']}}}
    pairs = AllPairsTopology.from_config(config['topologies']['sample_network'], mixed_type_soa)

    # Pick a real agent ID from the population
    agent_ids = list(mixed_type_soa['predator']['__ids__']) + list(mixed_type_soa['prey']['__ids__'])
    target_agent_id = str(agent_ids[random.randint(0, len(agent_ids) - 1)])

    neighbours = pairs.get_neighbours(target_agent_id, mixed_type_soa)
    assert target_agent_id not in neighbours
    assert len(neighbours) == len(agent_ids) - 1

def test_all_pairs_filters_by_agent_types(mixed_type_soa):
    config = {'topologies': {
        'sample_network': {'mode': 'all_pairs', 'agent_types': ['predator']}}}
    pairs = AllPairsTopology.from_config(config['topologies']['sample_network'], mixed_type_soa)

    # Pick a real agent ID from the population
    agent_ids = list(mixed_type_soa['predator']['__ids__'])
    target_agent_id = str(agent_ids[random.randint(0, len(agent_ids) - 1)])

    neighbours = pairs.get_neighbours(target_agent_id, mixed_type_soa)
    assert target_agent_id not in neighbours
    assert len(neighbours) == len(agent_ids) -1

def test_all_pairs_from_config_success(sample_soa):
    config = {'topologies': {
        'sample_network': {'mode': 'all_pairs', 'agent_types': ['person']}}}
    pairs = AllPairsTopology.from_config(config['topologies']['sample_network'], sample_soa)

    assert pairs.allow_self_interaction == False
    assert pairs.agent_types == ['person']

def test_all_pairs_single_agent_returns_empty(sample_soa_single_agent):
    config = {'topologies': {
        'sample_network': {'mode': 'all_pairs', 'agent_types': ['person']}}}
    pairs = AllPairsTopology.from_config(config['topologies']['sample_network'], sample_soa_single_agent)

    # Pick a real agent ID from the population
    agent_ids = list(sample_soa_single_agent['person']['__ids__'])
    target_agent_id = str(agent_ids[0])

    neighbours = pairs.get_neighbours(target_agent_id, sample_soa_single_agent)

    assert len(neighbours) == 0