import pytest
from typing import Any

from behaviour.condition import _evaluate_condition
from behaviour.expression_steps import (
    AssignmentStep,
    ConditionalRule,
    build_rule_steps,
)
from behaviour.expressions import run_rule_steps
from runner.state import AgentState

def make_agent(**attributes: Any) -> AgentState:
    """Build an AgentState carrying the given attributes for condition tests.

    Args:
        **attributes: Attribute name/value pairs stored in ``AgentState.state``,
            e.g. ``status="I"``, ``age=40``.

    Returns:
        A valid AgentState whose ``state`` dict holds the given attributes.
    """
    return AgentState(agent_type_name="person", state=dict(attributes))


def test_later_steps_see_earlier_writes():  # your conftest factory
    agent = make_agent(a=1, b=0)
    steps = build_rule_steps(["a += 1", "b = state['a'] * 10"], topology_names=[])
    run_rule_steps(steps, agent, lambda _t: [], lambda e, a: True)
    assert agent.get("a") == 2 and agent.get("b") == 20

'''
Integration tests (on expression steps)
'''

HUMAN_STEPS = [
    {"field": "age", "expression": "state['age'] + 1"},
    {
        "condition": "state['age'] >= 65",
        "then": [
            {"field": "employed", "expression": "False"},
        ],
        "else": [
            {"field": "employed", "expression": "state['employed']"},
            {"field": "weight_kg", "expression": "state['weight_kg'] - 1"},
        ],
    },
]


def _human(age: int, employed: bool = True, weight_kg: float = 70.0) -> AgentState:
    """Build a human AgentState with the attributes the rule touches."""
    return AgentState(
        agent_id="h1",
        agent_type_name="human",
        state={"age": age, "employed": employed, "weight_kg": weight_kg},
    )


def _run(agent: AgentState) -> None:
    """Compile HUMAN_STEPS and run them once against the agent."""
    steps = build_rule_steps(HUMAN_STEPS, topology_names=[])
    run_rule_steps(steps, agent, lambda _topology: [], _evaluate_condition)


def test_config_parses_into_expected_structure():
    steps = build_rule_steps(HUMAN_STEPS, topology_names=[])

    assert isinstance(steps[0], AssignmentStep)
    assert isinstance(steps[1], ConditionalRule)
    assert len(steps[1].then) == 1
    assert len(steps[1].else_) == 2  # the "else" key maps onto else_


def test_then_branch_sees_the_earlier_write():
    """64 -> 65 in step 1, so the condition (reached after) takes `then`."""
    agent = _human(age=64)
    _run(agent)

    assert agent.get("age") == 65
    assert agent.get("employed") is False
    assert agent.get("weight_kg") == 70.0  # else branch did not run


def test_else_branch_runs_every_step():
    agent = _human(age=30)
    _run(agent)

    assert agent.get("age") == 31
    assert agent.get("employed") is True
    assert agent.get("weight_kg") == 69.0  # second else step also ran


def test_then_branch_when_already_past_threshold():
    agent = _human(age=80)
    _run(agent)

    assert agent.get("employed") is False


def test_roundtrip_keeps_else_key():
    """to_config() must emit "else", not "else_"."""
    steps = build_rule_steps(HUMAN_STEPS, topology_names=[])
    dumped = steps[1].model_dump(by_alias=True)

    assert "else" in dumped and "else_" not in dumped


def test_unknown_key_in_conditional_is_rejected():
    bad = [{"condition": "True", "then": [], "elze": []}]
    with pytest.raises(ValueError):
        build_rule_steps(bad, topology_names=[])