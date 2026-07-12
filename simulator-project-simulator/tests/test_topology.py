import pytest

from topology.topology import TopologyProtocol, build_topologies
from topology.all_pairs import AllPairsTopology
from topology.random_sample import RandomSampleTopology
from topology.network import NetworkTopology


def test_generate_topology_protocol_success(sample_soa):
    config = {'topologies': {'sample_network_01': {'mode': 'random_sample', 'k': 2}, 'sample_network_02': {'mode': 'all_pairs', 'agent_types': ['person']}, 'sample_network_03': {'mode': 'network', 'agent_types': ['person'], 'graph': {'type': 'erdos_renyi', 'n': 10, 'p': 0.05, 'seed': 1}}}}

    result = build_topologies(config, sample_soa)

    assert 'sample_network_01' in result
    assert 'sample_network_02' in result
    assert 'sample_network_03' in result
    assert isinstance(result['sample_network_01'], TopologyProtocol)
    assert isinstance(result['sample_network_01'], RandomSampleTopology)
    assert isinstance(result['sample_network_02'], TopologyProtocol)
    assert isinstance(result['sample_network_02'], AllPairsTopology)
    assert isinstance(result['sample_network_03'], TopologyProtocol)
    assert isinstance(result['sample_network_03'], NetworkTopology)

def test_build_topologies_missing_section_raises(sample_soa):
    config = {}
    with pytest.raises(ValueError, match="must contain a 'topologies' section"):
        build_topologies(config, sample_soa)

def test_unknown_topology_raises_value_error(sample_soa):
    config = {'topologies': {'sample_network_01': {'mode': 'unknown'}}}

    with pytest.raises(ValueError, match='unknown mode') as e:
        build_topologies(config, sample_soa)
    assert "Expected one of: all_pairs, random_sample, network." in str(e.value)
