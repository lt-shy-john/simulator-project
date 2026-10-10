import pytest
import uuid
import random
from typing import Any

from behaviour.expressions import evaluate_expression, run_rule_steps
from behaviour.expression_steps import build_rule_steps, calls_neighbour_helper
from behaviour.condition import _evaluate_condition
from runner.state import AgentState
from stopping.expression import evaluate_condition

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

class FakeModel:
    """Minimal stand-in for the model object passed to S-10 conditions."""

    def __init__(self, counts: dict[str, int]) -> None:
        """Store canned ``count`` results.

        Args:
            counts: Mapping of count-expression -> number of matching agents.
        """
        self._counts = counts

    def count(self, expr: str) -> int:
        """Return the canned count for ``expr`` (0 if unknown).

        Args:
            expr: The agent-selection expression, e.g. ``"status==I"``.

        Returns:
            The number of agents matching ``expr``.
        """
        return self._counts.get(expr, 0)


def test_ternary_with_model_count_true_branch() -> None:
    """A ternary whose test uses model.count() takes the body when the test holds."""
    model = FakeModel({"status==I": 0, "status==S": 5})
    expr = 'True if model.count("status==I") == 0 else model.count("status==S") == 0'
    assert evaluate_condition(expr, model) is True


def test_ternary_with_model_count_false_branch() -> None:
    """The orelse branch is taken when the count-based test fails."""
    model = FakeModel({"status==I": 3, "status==S": 0})
    expr = 'False if model.count("status==I") == 0 else model.count("status==S") == 0'
    assert evaluate_condition(expr, model) is True


def test_nested_ternary_with_model_count() -> None:
    """Nested ternaries can chain several model.count() checks."""
    model = FakeModel({"status==I": 2, "status==E": 0})
    expr = (
        'False if model.count("status==I") == 0 '
        'else True if model.count("status==E") == 0 else False'
    )
    assert evaluate_condition(expr, model) is True

# ----------------------------------
# Test conditional with neighbours
# ----------------------------------

GAIN_STEP = [
    {
        "field": "energy",
        "expression": (
            "state['energy'] + 0.1 * max(0, "
            "sum(n['energy'] for n in neighbours) / len(neighbours)"
            " - state['energy']) if len(neighbours) > 0 "
            "else state['energy']"
        ),
        "topology_name": "contact",
    }
]


def _run(own_energy: float, neighbour_energies: list[float]) -> float:
    """Run the gain step for one agent and return its resulting energy."""
    agent = AgentState(
        agent_id="a1", agent_type_name="agent", state={"energy": own_energy}
    )
    neighbours = [
        AgentState(agent_id=f"n{i}", agent_type_name="agent", state={"energy": e})
        for i, e in enumerate(neighbour_energies)
    ]
    steps = build_rule_steps(GAIN_STEP, topology_names=["contact"])
    run_rule_steps(steps, agent, lambda _t: neighbours)
    return agent.get("energy")


def test_gains_when_neighbours_are_richer():
    # neighbour mean 80, own 60 -> 60 + 0.1 * 20
    assert _run(60.0, [80.0, 80.0]) == 62.0


def test_no_change_when_neighbours_are_poorer():
    assert _run(60.0, [40.0, 40.0]) == 60.0


# -------------------
# Neighbour helpers
# -------------------

def test_condition_can_use_neighbour_helper():
    agent = AgentState(
        agent_id="a1", agent_type_name="agent", state={"alert": False}
    )
    neighbours = [
        AgentState(agent_id="n1", agent_type_name="agent", state={"status": "I"}),
        AgentState(agent_id="n2", agent_type_name="agent", state={"status": "S"}),
    ]
    steps = build_rule_steps(
        [
            {
                "condition": """neighbor_count('state["status"] == "I"') > 0""",
                "then": [{"field": "alert", "expression": "True"}],
                "else": [],
            }
        ],
        topology_names=[],
    )

    run_rule_steps(steps, agent, lambda _t: neighbours)

    assert agent.get("alert") is True

@pytest.mark.parametrize(
    "expression, expected",
    [
        ("neighbor_count('state[\"x\"] > 1') > 0", True),   # helper call
        ("sum(n['e'] for n in neighbours)", True),          # `neighbours` name
        ("state['neighbor_count'] + 1", False),             # substring only, no Call
        ("state['energy'] - 0.5", False),
    ],
)
def test_calls_neighbour_helper_detection(expression, expected):
    assert calls_neighbour_helper(expression) is expected


def test_neighbours_name_requires_topology_with_two_topologies():
    raw = [{"field": "e", "expression": "sum(n['e'] for n in neighbours)"}]

    build_rule_steps(raw, topology_names=["a"])  # one topology: fine
    with pytest.raises(ValueError):
        build_rule_steps(raw, topology_names=["a", "b"])