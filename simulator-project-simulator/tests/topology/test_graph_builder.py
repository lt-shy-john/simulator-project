import pytest
import networkx as nx
import tempfile
import os

from topology.graph_builder import build_graph

def test_build_graph_by_erdos_renyi_success(sample_soa):
    config = {'mode': 'network', 'graph': {'type': 'erdos_renyi', 'n': 10, 'p': 0.5, 'seed': 1}}
    generated_graph = build_graph(config['graph'], sample_soa)

    agent_ids = set(str(id_) for id_ in sample_soa['person']['__ids__'])
    assert set(generated_graph.nodes()) == agent_ids

def test_build_graph_by_barabasi_albert_success(sample_soa):
    config = {'mode': 'network', 'graph': {'type': 'barabasi_albert', 'n': 10, 'm': 2, 'seed': 1}}
    generated_graph = build_graph(config['graph'], sample_soa)

    agent_ids = set(str(id_) for id_ in sample_soa['person']['__ids__'])
    assert set(generated_graph.nodes()) == agent_ids

def test_build_graph_by_watts_strogatz_success(sample_soa):
    config = {'mode': 'network', 'graph': {'type': 'watts_strogatz', 'n': 10, 'k': 3, 'p': 0.33, 'seed': 1}}
    generated_graph = build_graph(config['graph'], sample_soa)

    agent_ids = set(str(id_) for id_ in sample_soa['person']['__ids__'])
    assert set(generated_graph.nodes()) == agent_ids

def test_build_graph_by_algorithm_with_excess_n_throws_value_error(sample_soa):
    config = {'mode': 'network', 'graph': {'type': 'erdos_renyi', 'n': 10000, 'p': 0.5, 'seed': 1}}
    with pytest.raises(ValueError) as e:
        build_graph(config['graph'], sample_soa)
    assert e.match(f'n={config['graph']["n"]} does not match total agent')

def test_build_graph_by_unknown_algorithm_throws_value_error(sample_soa):
    config = {'mode': 'network', 'graph': {'type': 'unknown', 'n': 10, 'k': 3, 'p': 0.33, 'seed': 1}}
    with pytest.raises(ValueError) as e:
        build_graph(config['graph'], sample_soa)
    assert "Unknown graph type" in str(e.value)

def test_build_graph_by_graphml_file_success(sample_soa):
    agent_ids = [str(id_) for id_ in sample_soa['person']['__ids__']]
    graph = nx.Graph()
    graph.add_nodes_from(agent_ids)
    # Ensure every node has at least one edge before adding random extras
    for i in range(len(agent_ids)):
        graph.add_edge(agent_ids[i], agent_ids[(i + 1) % len(agent_ids)])

    try:
        with tempfile.NamedTemporaryFile(suffix='.graphml', delete=False) as f:
            path = f.name
        nx.write_graphml(graph, path)
        config = {'mode': 'network', 'source': path}
        generated_graph = build_graph(config, sample_soa)

        assert set(generated_graph.nodes()) == set(graph.nodes())
        assert set(map(frozenset, generated_graph.edges())) == set(map(frozenset, graph.edges()))
    finally:
        os.remove(path)


def test_build_graph_by_gml_file_success(sample_soa):
    agent_ids = [str(id_) for id_ in sample_soa['person']['__ids__']]
    graph = nx.Graph()
    graph.add_nodes_from(agent_ids)
    # Ensure every node has at least one edge before adding random extras
    for i in range(len(agent_ids)):
        graph.add_edge(agent_ids[i], agent_ids[(i + 1) % len(agent_ids)])

    try:
        with tempfile.NamedTemporaryFile(suffix='.gml', delete=False) as f:
            path = f.name
        nx.write_gml(graph, path)
        config = {'mode': 'network', 'source': path}
        generated_graph = build_graph(config, sample_soa)

        assert set(generated_graph.nodes()) == set(graph.nodes())
        assert set(map(frozenset, generated_graph.edges())) == set(map(frozenset, graph.edges()))
    finally:
        os.remove(path)

def test_build_graph_by_edgelist_file_success(sample_soa):
    agent_ids = [str(id_) for id_ in sample_soa['person']['__ids__']]
    graph = nx.Graph()
    graph.add_nodes_from(agent_ids)
    # Ensure every node has at least one edge before adding random extras
    for i in range(len(agent_ids)):
        graph.add_edge(agent_ids[i], agent_ids[(i + 1) % len(agent_ids)])

    try:
        with tempfile.NamedTemporaryFile(suffix='.edgelist', delete=False) as f:
            path = f.name
        nx.write_edgelist(graph, path)
        config = {'mode': 'network', 'source': path}
        generated_graph = build_graph(config, sample_soa)

        assert set(generated_graph.nodes()) == set(graph.nodes())
        assert set(map(frozenset, generated_graph.edges())) == set(map(frozenset, graph.edges()))
    finally:
        os.remove(path)

def test_build_graph_by_adjlist_file_success(sample_soa):
    agent_ids = [str(id_) for id_ in sample_soa['person']['__ids__']]
    graph = nx.Graph()
    graph.add_nodes_from(agent_ids)
    # Ensure every node has at least one edge before adding random extras
    for i in range(len(agent_ids)):
        graph.add_edge(agent_ids[i], agent_ids[(i + 1) % len(agent_ids)])

    try:
        with tempfile.NamedTemporaryFile(suffix='.adjlist', delete=False) as f:
            path = f.name
        nx.write_adjlist(graph, path)
        config = {'mode': 'network', 'source': path}
        generated_graph = build_graph(config, sample_soa)

        assert set(generated_graph.nodes()) == set(graph.nodes())
        assert set(map(frozenset, generated_graph.edges())) == set(map(frozenset, graph.edges()))
    finally:
        os.remove(path)

def test_build_graph_file_with_mismatched_node_ids_raises(sample_soa):
    graph = nx.erdos_renyi_graph(n=10, p=0.5, seed=1)  # default integer node labels, not UUIDs

    try:
        with tempfile.NamedTemporaryFile(suffix='.graphml', delete=False) as f:
            path = f.name
        nx.write_graphml(graph, path)
        config = {'source': path}
        with pytest.raises(ValueError, match="do not match"):
            build_graph(config, sample_soa)
    finally:
        os.remove(path)

def test_build_graph_no_source_type_throws_value_error(sample_soa):
    config = {'sample_network': {'mode': 'network', 'agent_types': 'person', 'graph': {'n': 10, 'p': 0.05, 'seed': 1}}}
    with pytest.raises(ValueError) as e:
        build_graph(config['sample_network']['graph'], sample_soa)
    assert e.match("Graph config must contain either 'source' or 'type'.")