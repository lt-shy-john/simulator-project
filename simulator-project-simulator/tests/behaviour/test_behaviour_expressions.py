import pytest
import uuid
import random
from typing import Any

from behaviour.expressions import evaluate_expression
from behaviour.condition import _evaluate_condition
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

"""
Ternary (conditional) expression tests for the shared simpleeval sandbox,
exercised through the S-10 stopping-condition evaluator.
"""

def make_agent(**attributes: Any) -> AgentState:
    """Build an AgentState carrying the given attributes for condition tests.

    Args:
        **attributes: Attribute name/value pairs stored in ``AgentState.state``,
            e.g. ``status="I"``, ``age=40``.

    Returns:
        A valid AgentState whose ``state`` dict holds the given attributes.
    """
    return AgentState(agent_type_name="person", state=dict(attributes))


# --- Single ternary ---------------------------------------------------------


@pytest.mark.parametrize(
    "status, age, expected",
    [
        ("I", 10, True),   # test true  -> body (True)
        ("S", 70, True),   # test false -> orelse (age > 60)
        ("S", 30, False),  # test false -> orelse (age > 60)
    ],
)
def test_single_ternary(status: str, age: int, expected: bool) -> None:
    """A single ternary selects the correct branch and returns a bool."""
    agent = make_agent(status=status, age=age)
    expr = "True if state['status'] == 'I' else state['age'] > 60"
    assert _evaluate_condition(expr, agent) is expected


# --- Nested ternary ---------------------------------------------------------


@pytest.mark.parametrize(
    "status, age, expected",
    [
        ("S", 10, True),   # first test true  -> age < 18
        ("S", 40, False),  # first test true  -> age < 18
        ("E", 40, True),   # second test true -> age < 65
        ("E", 70, False),  # second test true -> age < 65
        ("I", 40, False),  # fallthrough      -> False
    ],
)
def test_nested_ternary(status: str, age: int, expected: bool) -> None:
    """a if c1 else b if c2 else c resolves right-associatively."""
    expr = (
        "state['age'] < 18 if state['status'] == 'S' "
        "else state['age'] < 65 if state['status'] == 'E' else False"
    )
    assert _evaluate_condition(expr, make_agent(status=status, age=age)) is expected


def test_nested_ternary_has_no_depth_cap() -> None:
    """Deeply nested ternaries are not rejected by the sandbox."""
    depth = 30
    chain = (
        "".join(f"True if state['age'] == {i} else " for i in range(1, depth + 1))
        + "False"
    )
    assert _evaluate_condition(chain, make_agent(age=depth)) is True
    assert _evaluate_condition(chain, make_agent(age=depth + 1)) is False


# --- Short-circuiting and composition ---------------------------------------


def test_unused_branch_not_evaluated() -> None:
    """The branch not taken is never evaluated (no ZeroDivisionError)."""
    agent = make_agent(age=0)
    expr = "True if state['age'] == 0 else 10 / state['age'] > 1"
    assert _evaluate_condition(expr, agent) is True


def test_ternary_combined_with_boolean_operators() -> None:
    """Ternary composes with and/or when parenthesised."""
    agent = make_agent(status="I", age=40)
    expr = "(True if state['status'] == 'I' else False) and state['age'] > 18"
    assert _evaluate_condition(expr, agent) is True


# --- Sandbox still enforced inside ternaries --------------------------------


def test_unsafe_call_in_taken_branch_still_blocked() -> None:
    """Sandbox restrictions still apply to a ternary branch that is evaluated."""
    with pytest.raises(ValueError):
        _evaluate_condition("__import__('os') if True else False", make_agent(age=1))


def test_non_bool_ternary_result_rejected() -> None:
    """A ternary that yields a non-bool is rejected, like any other condition."""
    with pytest.raises(ValueError):
        _evaluate_condition("'a' if True else 'b'", make_agent(age=1))
