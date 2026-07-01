import pytest

from agents.agents import AgentType
from agents.attributeDefinition import AttributeDefinition
from agents.distributions import FixedDistribution, UniformDistribution, BinomialDistribution, PoissonDistribution, NormalDistribution, CategoricalDistribution
from agents.models import AttributeType, GenerationMode, PopulationMethod, PopulationStatus

def test_generate_agents_success():
    person01 = AgentType(name="person", count=10, generation_mode=GenerationMode.HOMOGENEOUS)
    assert person01.name == "person"
    assert person01.count == 10
    assert person01.generation_mode == GenerationMode.HOMOGENEOUS
    assert person01.attributes == []
    assert person01.status == PopulationStatus.NOT_CONFIGURED

def test_generate_no_agents_throws_exception():
    with pytest.raises(ValueError):
        person01 = AgentType(name="person", count=0, generation_mode=GenerationMode.HOMOGENEOUS)

def test_generate_negative_agents_throws_exception():
    with pytest.raises(ValueError):
        person01 = AgentType(name="person", count=-1, generation_mode=GenerationMode.HOMOGENEOUS)

def test_generate_float_number_agents_throws_exception():
    with pytest.raises(ValueError):
        person01 = AgentType(name="person", count=1.5, generation_mode=GenerationMode.HOMOGENEOUS)

def test_duplicate_attr_name_throws_exception():
    with pytest.raises(ValueError):
        field01 = AttributeDefinition(name='same_field_name')
        field02 = AttributeDefinition(name='same_field_name')
        person01 = AgentType(name="person", count=1, generation_mode=GenerationMode.HOMOGENEOUS, attributes=[field01, field02])

def test_agent_status_not_populated():
    person01 = AgentType(name="person", count=10, generation_mode=GenerationMode.HOMOGENEOUS)
    assert person01.status == PopulationStatus.NOT_CONFIGURED


def test_homogeneous_agent_status_success():
    energy = AttributeDefinition(name="energy", type=AttributeType.FLOAT)
    aggression = AttributeDefinition(name="aggression", type=AttributeType.INT)
    person01 = AgentType(
        name="person",
        count=10,
        generation_mode=GenerationMode.HOMOGENEOUS,
        attributes=[energy, aggression]
    )
    assert person01.status == PopulationStatus.COMPLETE


def test_heterogeneous_agent_status_success():
    energy = AttributeDefinition(
        name="energy",
        type=AttributeType.FLOAT,
        population_method=PopulationMethod.DISTRIBUTION,
        distribution=NormalDistribution(mean=100, stddev=15)
    )
    aggression = AttributeDefinition(
        name="aggression",
        type=AttributeType.INT,
        population_method=PopulationMethod.DISTRIBUTION,
        distribution=UniformDistribution(low=0, high=10)
    )
    person01 = AgentType(
        name="person",
        count=10,
        generation_mode=GenerationMode.HETEROGENEOUS,
        attributes=[energy, aggression]
    )
    assert person01.status == PopulationStatus.COMPLETE

def test_heterogeneous_agent_status_schema_only():
    energy = AttributeDefinition(name="energy", type=AttributeType.FLOAT)
    person01 = AgentType(
        name="person",
        count=10,
        generation_mode=GenerationMode.HETEROGENEOUS,
        attributes=[energy]
    )
    assert person01.status == PopulationStatus.SCHEMA_ONLY

def test_heterogeneous_agent_status_pending_import():
    energy = AttributeDefinition(
        name="energy",
        type=AttributeType.FLOAT,
        population_method=PopulationMethod.BULK_UPLOAD
    )
    person01 = AgentType(
        name="person",
        count=10,
        generation_mode=GenerationMode.HETEROGENEOUS,
        attributes=[energy],
        bulk_upload_template_path="agent_person_template.csv"
    )
    assert person01.status == PopulationStatus.PENDING_IMPORT

def test_attribute_distribution_method_without_distribution_raises():
    with pytest.raises(ValueError):
        AttributeDefinition(
            name="energy",
            type=AttributeType.FLOAT,
            population_method=PopulationMethod.DISTRIBUTION
        )

def test_attribute_distribution_set_without_method_raises():
    with pytest.raises(ValueError):
        AttributeDefinition(
            name="energy",
            type=AttributeType.FLOAT,
            population_method=PopulationMethod.MANUAL,
            distribution=NormalDistribution(mean=100, stddev=15)
        )

def test_agent_validate_success():
    person01 = AgentType.model_validate({
        "name": "person",
        "count": 10,
        "generation_mode": "homogeneous",
        "attributes": [
            {"name": "energy", "type": "float"},
            {"name": "aggression", "type": "int"}
        ],
    })
    assert person01.name == "person"
    assert person01.count == 10
    assert person01.generation_mode == GenerationMode.HOMOGENEOUS
    assert len(person01.attributes) == 2
    assert person01.status == PopulationStatus.COMPLETE
