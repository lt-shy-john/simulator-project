import pytest
import uuid
import random

from behaviour.expressions import evaluate_expression
from runner.state import AgentState

def test_evaluate_expression_success(sample_agents_dict):
    cmd_ls = ['state["energy"] -= 1', 'state["energy"] += 1', 'state["energy"] *= 3', 'state["energy"] /= 2', 'state["energy"] = 2.1']
    results = []

    i = 0
    for id, agent_state in sample_agents_dict.items():
        agent_state.state["energy"] = 1  # Set the energy value instead of random
        evaluate_expression(cmd_ls[(i+1)%len(cmd_ls)-1], agent_state, None)
        results.append((cmd_ls[(i+1)%len(cmd_ls)-1], sample_agents_dict[id]))
        i += 1

    for result in results:
        if result[0] == cmd_ls[0]:
            assert result[1].state["energy"] == 0
        elif result[0] == cmd_ls[1]:
            assert result[1].state["energy"] == 2
        elif result[0] == cmd_ls[2]:
            assert result[1].state["energy"] == 3
        elif result[0] == cmd_ls[3]:
            assert result[1].state["energy"] == 0.5
        elif result[0] == cmd_ls[4]:
            assert result[1].state["energy"] == 2.1

def test_evaluate_expression_with_network_success(sample_agents_dict):
    target_agent = random.choice(list(sample_agents_dict.values()))
    target_agent.state["infected"] = False
    neighbour_1 = AgentState(agent_id=str(uuid.uuid4()), agent_type_name='person', state={"infected": False})
    neighbour_2 = AgentState(agent_id=str(uuid.uuid4()), agent_type_name='person', state={"infected": True})
    neighbours_state = [neighbour_1.state, neighbour_2.state]
    evaluate_expression('state["infected"] = any(n["infected"] for n in neighbours)', target_agent, neighbours_state)

    assert target_agent.state["infected"] == True

def test_evaluate_expression_invalid_expr_throws_value_error(sample_agents_dict):
    cmd_ls = ['state["energy"] m= 1', 'state["energy"] p= 1', 'state["energy"] t= 3', 'state["energy"] d= 2',
              'state["energy"] == 2.1']
    results = []

    i = 0
    with pytest.raises(ValueError) as e:
        for id, agent_state in sample_agents_dict.items():
            agent_state.state["energy"] = 1  # Set the energy value instead of random
            evaluate_expression(cmd_ls[(i + 1) % len(cmd_ls) - 1], agent_state, None)
            results.append((cmd_ls[(i + 1) % len(cmd_ls) - 1], sample_agents_dict[id]))
            i += 1

def test_evaluate_expression_divide_zero_raises_value_error(sample_agents_dict):
    agent = list(sample_agents_dict.values())[0]
    with pytest.raises(ValueError):
        evaluate_expression('state["energy"] /= 0', agent, [])

def test_evaluate_expression_syntax_error_raises_value_error(sample_agents_dict):
    agent = list(sample_agents_dict.values())[0]
    agent.state["energy"] = 10
    with pytest.raises(ValueError):
        evaluate_expression('state["energy"] += 1 +', agent, [])

def test_evaluate_expression_type_error_raises_value_error(sample_agents_dict):
    agent = list(sample_agents_dict.values())[0]
    agent.state["energy"] = 10
    with pytest.raises(ValueError):
        evaluate_expression('state["energy"] += "abc"', agent, [])

def test_evaluate_expression_undefined_name_raises_value_error(sample_agents_dict):
    agent = list(sample_agents_dict.values())[0]
    with pytest.raises(ValueError):
        evaluate_expression('state["energy"] = undefined_variable', agent, [])