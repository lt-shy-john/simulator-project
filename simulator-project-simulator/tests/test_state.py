import pytest
import uuid
import random
import numpy as np

from runner.state import _sample_distribution, AgentState, initialise_population, apply_snapshot_updates
from agents.attributeDefinition import AttributeDefinition
from agents.models import AttributeType, GenerationMode, PopulationMethod
from agents.distributions import FixedDistribution, UniformDistribution, BinomialDistribution, PoissonDistribution, NormalDistribution, CategoricalDistribution
from agents.agents import AgentType

def test_generate_agent_state_success():
    agent_id = str(uuid.uuid4())
    agent_state = AgentState(agent_id=agent_id, agent_type_name='person', state={})
    assert agent_state.agent_id == agent_id
    assert agent_state.agent_type_name == 'person'
    assert agent_state.state == {}
    assert len(agent_state.state) == 0
    assert agent_state.model_config['arbitrary_types_allowed'] is True
    assert agent_state.mutation_count == 0

def test_generate_agent_unicode_state_name_success():
    # Right now we can allow Unicode state names
    agent_id = str(uuid.uuid4())
    agent_state = AgentState(agent_id=agent_id, agent_type_name='person', state={'能量': 100, 'énergie': 50.0})
    assert agent_state.agent_id == agent_id
    assert len(agent_state.state) == 2

def test_generate_agent_duplicate_state_and_value_merges():
    agent_state = AgentState(agent_id=str(uuid.uuid4()), agent_type_name='person', state={'state1': 1, 'state1': 1})
    assert len(agent_state.state) == 1
    assert agent_state.state['state1'] == 1

def test_generate_agent_duplicate_state_key_last_value_wins():
    agent_state = AgentState(agent_id=str(uuid.uuid4()), agent_type_name='person', state={'state1': 1, 'state1': 2})
    assert len(agent_state.state) == 1
    assert agent_state.state['state1'] == 2  # last value wins

def test_get_defined_attribute_returns_value():
    agent_state = AgentState(agent_id=str(uuid.uuid4()), agent_type_name='person', state={'state1': 42})
    assert agent_state.get('state1') == 42

def test_get_undefined_attribute_raises_keyerror():
    agent_state = AgentState(agent_id=str(uuid.uuid4()), agent_type_name='person', state={'state1': 1})
    with pytest.raises(KeyError):
        agent_state.get('state2')

def test_set_undefined_attribute_raises_keyerror():
    agent_state = AgentState(agent_id=str(uuid.uuid4()), agent_type_name='person', state={'state1': 1})
    with pytest.raises(KeyError):
        agent_state.set('state2', 2)

def test_set_increments_mutation_count():
    agent_state = AgentState(agent_id=str(uuid.uuid4()), agent_type_name='person', state={'state1': 1})
    agent_state.set('state1', 1)
    assert agent_state.mutation_count == 1
    agent_state.set('state1', 3)
    assert agent_state.mutation_count == 2

def test_sample_normal_distribution_returns_correct_count():
    distro = NormalDistribution(mean=0, stddev=1)
    attr_def01 = AttributeDefinition(name='attr01', type=AttributeType.FLOAT, population_method=PopulationMethod.DISTRIBUTION, distribution=distro)
    count = 100
    result = _sample_distribution(attr_def01, count)
    assert len(result) == count
    assert isinstance(result, np.ndarray)
    assert -0.5 < result.mean() < 0.5

def test_sample_uniform_distribution_within_bounds():
    distro = UniformDistribution(low=0, high=1)
    attr_def01 = AttributeDefinition(name='attr01', type=AttributeType.FLOAT,
                                     population_method=PopulationMethod.DISTRIBUTION,
                                     distribution=distro)
    count = 100
    result = _sample_distribution(attr_def01, count)
    assert len(result) == count
    assert isinstance(result, np.ndarray)
    for data in result:
        assert distro.low < data < distro.high

def test_sample_fixed_distribution_all_same_value():
    distro = FixedDistribution(value=1)
    attr_def01 = AttributeDefinition(name='attr01', type=AttributeType.FLOAT,
                                     population_method=PopulationMethod.DISTRIBUTION,
                                     distribution=distro)
    count = 100
    result = _sample_distribution(attr_def01, count)
    assert len(result) == count
    assert isinstance(result, np.ndarray)
    for data in result:
        assert data == 1

def test_distribution_wrong_population_method_throws_value_error():
    with pytest.raises(ValueError):
        AttributeDefinition(name='attr01', type=AttributeType.FLOAT, population_method=PopulationMethod.MANUAL, distribution=NormalDistribution(mean=0, stddev=1))

def test_snapshot_is_deep_copy():
    agent_state = AgentState(agent_id=str(uuid.uuid4()), agent_type_name='person', state={'state1': 1})
    copy = agent_state.snapshot()
    assert isinstance(copy, AgentState)

    # Change original state and compare
    agent_state.set('state1', 2)
    assert agent_state.state['state1'] == 2
    assert copy.state['state1'] == 1  # copy retains original value
    assert agent_state.state['state1'] != copy.state['state1']

def test_initialise_population_success():
    count = 10
    person01 = AgentType(name="person", count=count, generation_mode=GenerationMode.HOMOGENEOUS)
    agent_state = AgentState(agent_id=str(uuid.uuid4()), agent_type_name='person', state={'state1': 1})

    result = initialise_population(person01)

    assert len(result) == count
    for person in result:
        assert isinstance(person, AgentState)


def test_snapshot_update_success():
    energy = AttributeDefinition(
        name='state1',
        type=AttributeType.INT,
        population_method=PopulationMethod.DISTRIBUTION,
        distribution=UniformDistribution(low=1, high=10)
    )
    count = 10
    person01 = AgentType(name="person", count=count, generation_mode=GenerationMode.HOMOGENEOUS, attributes=[energy])
    population = initialise_population(person01)

    # Take snapshots and modify one
    snapshots = [agent.snapshot() for agent in population]
    target_idx = random.randint(0, len(population) - 1)
    snapshots[target_idx].set('state1', 2)

    result = apply_snapshot_updates(population, snapshots)
    assert result[target_idx].state['state1'] == 99