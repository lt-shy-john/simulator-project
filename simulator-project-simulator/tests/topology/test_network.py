import pytest
import random
import networkx as nx

from topology.network import NetworkTopology

def test_network_from_config_generates_graph_success(sample_soa):
    config = {'mode': 'network', 'agent_types': ['person'], 'graph': {'type': 'erdos_renyi', 'n': 10, 'p': 0.5, 'seed': 1}}
    result = NetworkTopology.from_config(config, sample_soa)

    assert isinstance(result, NetworkTopology)
    assert result.agent_types == ['person']

def test_network_from_config_missing_graph_section_raises(sample_soa):
    config = {'mode': 'network', 'agent_types': ['person']}
    with pytest.raises(ValueError) as e:
        NetworkTopology.from_config(config, sample_soa)
    assert "Network topology config must contain a 'graph' section." in str(e.value)

def test_network_get_neighbours_returns_adjacent_nodes(sample_soa):
    config = {'mode': 'network', 'agent_types': ['person'],
              'graph': {'type': 'erdos_renyi', 'n': 10, 'p': 0.5, 'seed': 1}}
    graph = NetworkTopology.from_config(config, sample_soa)

    agent_ids = list(sample_soa['person']['__ids__'])
    target_agent_id = str(agent_ids[random.randint(0, len(agent_ids) - 1)])

    neighbours = graph.get_neighbours(target_agent_id, sample_soa)
    expected = list(graph.graph.neighbors(target_agent_id))

    assert set(neighbours) == set(expected)

def test_network_get_neighbours_excludes_self_by_default(sample_soa):
    config = {'mode': 'network', 'agent_types': ['person'],
              'graph': {'type': 'erdos_renyi', 'n': 10, 'p': 0.5, 'seed': 1}}
    generated_graph = NetworkTopology.from_config(config, sample_soa)

    agent_ids = list(sample_soa['person']['__ids__'])
    target_agent_id = str(agent_ids[random.randint(0, len(agent_ids) - 1)])

    neighbours = generated_graph.get_neighbours(target_agent_id, sample_soa)

    assert target_agent_id not in neighbours

def test_network_get_neighbours_isolated_node_returns_empty(sample_soa):
    agent_ids = [str(id_) for id_ in sample_soa['person']['__ids__']]
    graph = nx.Graph()
    graph.add_nodes_from(agent_ids)

    topology = NetworkTopology(graph=graph)

    target_agent_id = agent_ids[0]
    neighbours = topology.get_neighbours(target_agent_id, sample_soa)

    assert neighbours == []

def test_network_get_neighbours_agent_not_in_graph_returns_empty(sample_soa):
    agent_ids = [str(id_) for id_ in sample_soa['person']['__ids__']]
    graph = nx.Graph()
    graph.add_nodes_from(agent_ids)

    target_agent_id = agent_ids[0]
    graph.remove_node(target_agent_id)

    topology = NetworkTopology(graph=graph)

    neighbours = topology.get_neighbours(target_agent_id, sample_soa)

    assert neighbours == []

def test_network_filters_by_agent_types(mixed_type_soa):
    config = {'mode': 'network', 'agent_types': ['predator'],
              'graph': {'type': 'erdos_renyi', 'n': 10, 'p': 0.5, 'seed': 1}}
    generated_graph = NetworkTopology.from_config(config, mixed_type_soa)

    assert isinstance(generated_graph, NetworkTopology)
    assert generated_graph.agent_types == ['predator']

    predator_ids = list(mixed_type_soa['predator']['__ids__'])
    target_agent_id = str(predator_ids[0])
    neighbours = generated_graph.get_neighbours(target_agent_id, mixed_type_soa)
    prey_ids = set(str(id_) for id_ in mixed_type_soa['prey']['__ids__'])
    assert not any(n in prey_ids for n in neighbours)

def test_network_invalid_agent_type_raises(sample_soa):
    config = {'mode': 'network', 'agent_types': ['predator'],
              'graph': {'type': 'erdos_renyi', 'n': 10, 'p': 0.5, 'seed': 1}}
    with pytest.raises(ValueError) as e:
        NetworkTopology.from_config(config, sample_soa)
    assert 'agent_types contains unknown type(s): ' in str(e.value)