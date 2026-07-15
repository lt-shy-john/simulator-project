import pytest
import random

from topology.random_sample import RandomSampleTopology

def test_set_random_sample_topology_from_k_config_success(sample_soa):
    config = {'mode': 'random_sample', 'k': 5, 'seed': 42}
    topology = RandomSampleTopology.from_config(config, sample_soa)
    assert topology.k == 5
    assert topology.proportion is None

def test_set_random_sample_topology_from_prob_config_success(sample_soa):
    config = {'mode': 'random_sample', 'proportion': 0.5, 'seed': 42}
    topology = RandomSampleTopology.from_config(config, sample_soa)
    assert topology.proportion == 0.5
    assert topology.k is None

def test_set_random_sample_topology_from_k_and_prob_config_throws_value_error(sample_soa):
    config = {'mode': 'random_sample', 'k': 5, 'proportion': 0.5}
    with pytest.raises(ValueError):
        RandomSampleTopology.from_config(config, sample_soa)

def test_random_sample_rejects_invalid_proportion(sample_soa):
    config = {'mode': 'random_sample', 'proportion': 1.01, 'seed': 4}
    with pytest.raises(ValueError) as e:
        RandomSampleTopology.from_config(config, sample_soa)
    assert "proportion must be in (0.0, 1.0], got " in str(e.value)

def test_random_sample_rejects_invalid_k(sample_soa):
    config = {'mode': 'random_sample', 'k': 0, 'seed': 4}
    with pytest.raises(ValueError) as e:
        RandomSampleTopology.from_config(config, sample_soa)
    assert "k must be >= 1, got" in str(e.value)

def test_random_sample_fixed_k_returns_correct_count(sample_soa):
    config = {'mode': 'random_sample', 'k': 5, 'seed': 42}
    topology = RandomSampleTopology.from_config(config, sample_soa)

    # Pick a real agent ID from the population
    agent_ids = list(sample_soa['person']['__ids__'])
    target_agent_id = str(agent_ids[random.randint(0, len(agent_ids) - 1)])

    result = topology.get_neighbours(target_agent_id, sample_soa)

    assert len(result) == config['k']

def test_random_sample_fixed_k_excludes_self(sample_soa):
    config = {'mode': 'random_sample', 'k': 5, 'seed': 42}
    topology = RandomSampleTopology.from_config(config, sample_soa)

    # Pick a real agent ID from the population
    agent_ids = list(sample_soa['person']['__ids__'])
    target_agent_id = str(agent_ids[random.randint(0, len(agent_ids) - 1)])

    result = topology.get_neighbours(target_agent_id, sample_soa)

    assert target_agent_id not in result

def test_random_sample_fixed_k_capped_at_pool_size(sample_soa):
    pool_size = len(sample_soa['person']['__ids__'])
    config = {'mode': 'random_sample', 'k': random.randint(pool_size, 100), 'seed': 42}
    topology = RandomSampleTopology.from_config(config, sample_soa)

    # Pick a real agent ID from the population
    agent_ids = list(sample_soa['person']['__ids__'])
    target_agent_id = str(agent_ids[random.randint(0, len(agent_ids) - 1)])

    result = topology.get_neighbours(target_agent_id, sample_soa)

    assert len(result) == pool_size - 1

def test_random_sample_same_seed_produces_same_result(sample_soa):
    pool_size = len(sample_soa['person']['__ids__'])
    k = random.randint(1, pool_size - 1)

    config_01 = {'mode': 'random_sample', 'k': k, 'seed': 42}
    topology_01 = RandomSampleTopology.from_config(config_01, sample_soa)

    config_02 = {'mode': 'random_sample', 'k': k, 'seed': 42}
    topology_02 = RandomSampleTopology.from_config(config_02, sample_soa)

    # Pick a real agent ID from the population
    agent_ids = list(sample_soa['person']['__ids__'])
    target_agent_id = str(agent_ids[random.randint(0, len(agent_ids) - 1)])

    result_01 = topology_01.get_neighbours(target_agent_id, sample_soa)
    result_02 = topology_02.get_neighbours(target_agent_id, sample_soa)

    assert result_01 == result_02

def test_random_sample_different_seed_produces_different_result(sample_soa):
    pool_size = len(sample_soa['person']['__ids__'])
    agent_ids = list(sample_soa['person']['__ids__'])
    target_agent_id = str(agent_ids[0])

    results = []
    for seed in range(5):
        config = {'mode': 'random_sample', 'k': pool_size - 1, 'seed': seed}
        topology = RandomSampleTopology.from_config(config, sample_soa)
        results.append(tuple(topology.get_neighbours(target_agent_id, sample_soa)))

    assert len(set(results)) > 1  # at least some seeds produce different results

def test_random_sample_filters_by_agent_types(mixed_type_soa):
    config = {'mode': 'random_sample', 'k': 3, 'agent_types': ['predator']}
    topology = RandomSampleTopology.from_config(config, mixed_type_soa)

    predator_ids = list(mixed_type_soa['predator']['__ids__'])
    target_agent_id = str(predator_ids[0])

    result = topology.get_neighbours(target_agent_id, mixed_type_soa)

    prey_ids = set(str(id_) for id_ in mixed_type_soa['prey']['__ids__'])
    assert not any(n in prey_ids for n in result)

def test_random_sample_invalid_agent_type_raises(sample_soa):
    config = {'mode': 'random_sample', 'k': 5, 'agent_types': ['predator']}
    with pytest.raises(ValueError) as e:
        RandomSampleTopology.from_config(config, sample_soa)

def test_random_sample_empty_pool_returns_empty(sample_soa_single_agent):
    pool_size = len(sample_soa_single_agent['person']['__ids__'])
    config = {'mode': 'random_sample', 'k': random.randint(pool_size, 100), 'seed': 1}
    topology = RandomSampleTopology.from_config(config, sample_soa_single_agent)

    # Pick a real agent ID from the population
    agent_ids = list(sample_soa_single_agent['person']['__ids__'])
    target_agent_id = str(agent_ids[random.randint(0, len(agent_ids) - 1)])

    result = topology.get_neighbours(target_agent_id, sample_soa_single_agent)

    assert len(result) == 0