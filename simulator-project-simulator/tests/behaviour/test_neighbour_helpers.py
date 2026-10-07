import pytest

from behaviour.neighbour_helpers import make_neighbour_helpers
from runner.state import AgentState


def _agents(*rows: dict) -> list[AgentState]:
    """Build neighbour AgentStates from state dicts."""
    return [
        AgentState(agent_id=f"n{i}", agent_type_name="agent", state=dict(r))
        for i, r in enumerate(rows)
    ]


@pytest.fixture
def helpers():
    return make_neighbour_helpers(_agents(
        {"energy": 10.0, "status": "I"},
        {"energy": 30.0, "status": "S"},
        {"energy": 50.0, "status": "S"},
    ))


def test_count_unfiltered_and_filtered(helpers):
    assert helpers["neighbor_count"]() == 3
    assert helpers["neighbor_count"]("state['status'] == 'S'") == 2


def test_mean_with_and_without_filter(helpers):
    assert helpers["neighbor_mean"]("energy") == 30.0
    assert helpers["neighbor_mean"]("energy", "state['status'] == 'S'") == 40.0


def test_sum_with_and_without_filter(helpers):
    assert helpers["neighbor_sum"]("energy") == 90.0
    assert helpers["neighbor_sum"]("energy", "state['status'] == 'S'") == 80.0


def test_any_and_all(helpers):
    assert helpers["neighbor_any"]("state['status'] == 'I'") is True
    assert helpers["neighbor_any"]("state['status'] == 'R'") is False
    assert helpers["neighbor_all"]("state['energy'] > 5") is True
    assert helpers["neighbor_all"]("state['status'] == 'S'") is False


def test_empty_neighbourhood():
    h = make_neighbour_helpers([])
    assert h["neighbor_count"]() == 0
    assert h["neighbor_sum"]("energy") == 0
    assert h["neighbor_mean"]("energy") == 0.0
    assert h["neighbor_any"]("True") is False
    assert h["neighbor_all"]("True") is True  # vacuous truth
