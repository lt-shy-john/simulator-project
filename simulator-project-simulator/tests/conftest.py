import pytest
import random

from runner.soa import to_soa
from runner.state import AgentState
import uuid

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
def sample_agents_dict():
    ids = [str(uuid.uuid4()) for _ in range(10)]
    return {id: AgentState(agent_id=id, agent_type_name='person',
                             state={'energy': random.randint(0, 10)}) for id in ids}