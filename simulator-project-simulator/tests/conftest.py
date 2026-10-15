import pytest
import random

from agents.agents import AgentType
from agents.attributeDefinition import AttributeDefinition
from agents.distributions import UniformDistribution, FixedDistribution
from agents.models import AttributeType, GenerationMode, PopulationMethod
from runner.soa import to_soa
from runner.state import AgentState
import uuid

@pytest.fixture
def base_config() -> dict:
    """A minimal, fully valid config: one heterogeneous agent type with a
    single distribution-driven attribute, an all_pairs topology, one
    expression behaviour, all_at_once scheduling, and a max_steps stop."""
    return {
        "seed": 42,
        "agent_types": [
            {
                "name": "person",
                "count": 5,
                "generation_mode": "heterogeneous",
                "attributes": [
                    {
                        "name": "age",
                        "type": "int",
                        "population_method": "distribution",
                        "distribution": {"kind": "uniform", "low": 0, "high": 100},
                    },
                ],
            }
        ],
        "topologies": {
            "contact": {"mode": "all_pairs", "agent_types": ["person"]},
        },
        "behaviours": {
            "person": [
                {"expression": 'state["age"] += 1', "topology_name": "contact"},
            ],
        },
        "scheduler": {"order": "all_at_once", "read_mode": "frozen"},
        "stopping": {"max_steps": 3, "conditions": [], "combinator": "OR"},
    }

@pytest.fixture
def sample_soa():
    agents = [
        AgentState(agent_id=str(uuid.uuid4()), agent_type_name='person', state={'energy': i})
        for i in range(10)
    ]
    return to_soa(agents)

@pytest.fixture
def mixed_type_soa():
    agents = [
        AgentState(agent_id=str(uuid.uuid4()), agent_type_name='predator', state={'energy': i})
        for i in range(5)
    ] + [
        AgentState(agent_id=str(uuid.uuid4()), agent_type_name='prey', state={'energy': i})
        for i in range(5)
    ]
    return to_soa(agents)

@pytest.fixture
def sample_soa_single_agent():
    return to_soa([AgentState(agent_id=str(uuid.uuid4()), agent_type_name='person', state={'energy': 1})])

@pytest.fixture
def sample_single_agent_dict():
    id = str(uuid.uuid4())
    return {id: AgentState(agent_id=id, agent_type_name='person',
                             state={'energy': random.randint(0, 10)})}

@pytest.fixture
def sample_agents_dict():
    ids = [str(uuid.uuid4()) for _ in range(10)]
    return {id: AgentState(agent_id=id, agent_type_name='person',
                             state={'energy': random.randint(0, 10)}) for id in ids}

@pytest.fixture
def sample_agents_with_action_quota_dict():
    ids = [str(uuid.uuid4()) for _ in range(10)]
    return {id: AgentState(agent_id=id, agent_type_name='person',
                             state={'energy': random.randint(0, 10), 'actions_remaining': 3}) for id in ids}

@pytest.fixture
def predator_prey_agent_types():
    """Returns a dict[str, AgentType] with 'predator' and 'prey' types,
    each with an 'energy' attribute matching the keys used in
    mixed_type_soa-style fixtures elsewhere."""
    predator_energy = AttributeDefinition(
        name="energy",
        type=AttributeType.INT,
        population_method=PopulationMethod.DISTRIBUTION,
        distribution=UniformDistribution(low=1, high=10)
    )
    prey_energy = AttributeDefinition(
        name="energy",
        type=AttributeType.INT,
        population_method=PopulationMethod.DISTRIBUTION,
        distribution=UniformDistribution(low=1, high=10)
    )

    return {
        "predator": AgentType(
            name="predator",
            count=5,
            generation_mode=GenerationMode.HOMOGENEOUS,
            attributes=[predator_energy]
        ),
        "prey": AgentType(
            name="prey",
            count=5,
            generation_mode=GenerationMode.HOMOGENEOUS,
            attributes=[prey_energy]
        ),
    }


@pytest.fixture
def person_agent_types():
    """Returns a dict[str, AgentType] with a single 'person' type,
    with an 'energy' attribute matching the keys used in
    sample_agents_dict-style fixtures elsewhere."""
    energy_attr = AttributeDefinition(
        name="energy",
        type=AttributeType.INT,
        population_method=PopulationMethod.DISTRIBUTION,
        distribution=UniformDistribution(low=1, high=10)
    )

    return {
        "person": AgentType(
            name="person",
            count=10,
            generation_mode=GenerationMode.HOMOGENEOUS,
            attributes=[energy_attr]
        ),
    }