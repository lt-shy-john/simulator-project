import pytest

from behaviour.model import SimulationModel
from runner.state import AgentState
from stopping.expression import evaluate_condition


def _model_with_agents(states: list[dict]) -> SimulationModel:
    model = SimulationModel()
    model.agents = [
        AgentState(agent_type_name="person", state=s) for s in states
    ]
    return model


def test_count_condition_true():
    model = _model_with_agents([{"status": "I"}, {"status": "S"}])
    assert evaluate_condition('model.count("state[\\"status\\"]==\\"I\\"") == 1', model) is True


def test_count_condition_false():
    model = _model_with_agents([{"status": "I"}, {"status": "I"}])
    assert evaluate_condition('model.count("state[\\"status\\"]==\\"I\\"") == 0', model) is False


def test_count_no_filter_counts_all_agents():
    model = _model_with_agents([{"status": "I"}, {"status": "S"}, {"status": "R"}])
    assert evaluate_condition("model.count() == 3", model) is True


def test_mean_condition():
    model = _model_with_agents([{"energy": 10}, {"energy": 20}])
    assert evaluate_condition("model.mean(\"energy\") == 15", model) is True


def test_sum_condition():
    model = _model_with_agents([{"energy": 10}, {"energy": 20}, {"energy": 5}])
    assert evaluate_condition("model.sum(\"energy\") == 35", model) is True


def test_sum_condition_empty_population_is_zero_not_error():
    model = _model_with_agents([])
    assert evaluate_condition("model.sum(\"energy\") == 0", model) is True


def test_non_boolean_result_raises_value_error():
    model = _model_with_agents([{"energy": 10}])
    with pytest.raises(ValueError, match="did not evaluate to a boolean"):
        evaluate_condition("model.count()", model)  # returns int, not bool


def test_malformed_expression_raises_value_error():
    model = _model_with_agents([{"energy": 10}])
    with pytest.raises(ValueError):
        evaluate_condition("model.count( ==", model)


def test_proxy_blocks_unlisted_model_methods():
    """A condition expression must not be able to reach model.remove,
    model.log_event, or any method outside count/mean/sum."""
    model = _model_with_agents([{"energy": 10}])
    with pytest.raises(ValueError):
        evaluate_condition('model.remove("some_id")', model)


def test_proxy_blocks_agents_attribute_access():
    model = _model_with_agents([{"energy": 10}])
    with pytest.raises(ValueError):
        evaluate_condition("model.agents", model)