import pytest

from agents.agents import AgentType
from agents.attributeDefinition import AttributeDefinition
from agents.models import GenerationMode, PopulationStatus

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
