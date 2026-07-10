import pytest
import uuid
import numpy as np

from runner.soa import to_soa, from_soa, add_agent, remove_agent, SoAPopulation
from runner.state import _sample_distribution, AgentState, initialise_population, apply_snapshot_updates
from agents.attributeDefinition import AttributeDefinition
from agents.models import AttributeType, GenerationMode, PopulationMethod
from agents.distributions import UniformDistribution
from agents.agents import AgentType

def test_to_soa_success():
    low, high = (1, 10)
    agent_state = AttributeDefinition(
        name='state1',
        type=AttributeType.INT,
        population_method=PopulationMethod.DISTRIBUTION,
        distribution=UniformDistribution(low=low, high=high)
    )
    count = 10
    person01 = AgentType(name="person", count=count, generation_mode=GenerationMode.HOMOGENEOUS, attributes=[agent_state])
    population = initialise_population(person01)

    result = to_soa(population)
    assert np.max(result['person']['state1']) <= high
    assert np.min(result['person']['state1']) >= low
    assert 'person' in result
    assert len(result['person']['__ids__']) == count
    assert 'state1' in result['person']

def test_from_soa_success():
    low, high = (1, 10)
    agent_state = AttributeDefinition(
        name='state1',
        type=AttributeType.INT,
        population_method=PopulationMethod.DISTRIBUTION,
        distribution=UniformDistribution(low=low, high=high)
    )
    count = 10
    person01 = AgentType(name="person", count=count, generation_mode=GenerationMode.HOMOGENEOUS,
                         attributes=[agent_state])
    population = initialise_population(person01)
    result = to_soa(population)

    result = from_soa(result)
    assert len(result) == count
    original_ids = {a.agent_id for a in population}
    result_ids = {a.agent_id for a in result}
    assert original_ids == result_ids
    for person in result:
        assert isinstance(person, AgentState)

def test_soa_add_agent_success():
    low, high = (1, 10)
    agent_state = AttributeDefinition(
        name='state1',
        type=AttributeType.INT,
        population_method=PopulationMethod.DISTRIBUTION,
        distribution=UniformDistribution(low=low, high=high)
    )
    count = 10
    person01 = AgentType(name="person", count=count, generation_mode=GenerationMode.HOMOGENEOUS,
                         attributes=[agent_state])
    population = initialise_population(person01)
    population_array = to_soa(population)

    new_agent = AgentState(
        agent_id=str(uuid.uuid4()),
        agent_type_name='person',
        state={'state1': 5}
    )

    result = add_agent(population_array, new_agent)
    assert len(result['person']['__ids__']) == count+1

def test_soa_add_agent_new_type_success():
    pass

def test_soa_remove_agent_success():
    low, high = (1, 10)
    agent_state = AttributeDefinition(
        name='state1',
        type=AttributeType.INT,
        population_method=PopulationMethod.DISTRIBUTION,
        distribution=UniformDistribution(low=low, high=high)
    )
    count = 10
    person01 = AgentType(name="person", count=count, generation_mode=GenerationMode.HOMOGENEOUS,
                         attributes=[agent_state])
    population = initialise_population(person01)
    population_array = to_soa(population)

    result = remove_agent(population_array, population[0].agent_id)
    assert len(result['person']['__ids__']) == count-1

def test_soa_remove_last_agent_removes_type_entry():
    low, high = (1, 10)
    agent_state = AttributeDefinition(
        name='state1',
        type=AttributeType.INT,
        population_method=PopulationMethod.DISTRIBUTION,
        distribution=UniformDistribution(low=low, high=high)
    )
    count = 1
    person01 = AgentType(name="person", count=count, generation_mode=GenerationMode.HOMOGENEOUS,
                         attributes=[agent_state])
    population = initialise_population(person01)
    population_array = to_soa(population)

    result = remove_agent(population_array, population[0].agent_id)
    assert len(result) == 0

def test_soa_remove_inexistent_agent_throws_exception():
    low, high = (1, 10)
    agent_state = AttributeDefinition(
        name='state1',
        type=AttributeType.INT,
        population_method=PopulationMethod.DISTRIBUTION,
        distribution=UniformDistribution(low=low, high=high)
    )
    count = 1
    person01 = AgentType(name="person", count=count, generation_mode=GenerationMode.HOMOGENEOUS,
                         attributes=[agent_state])
    population = initialise_population(person01)
    population_array = to_soa(population)

    remove_agent(population_array, population[0].agent_id)

    with pytest.raises(KeyError):
        remove_agent(population_array, population[0].agent_id)