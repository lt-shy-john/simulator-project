import pytest

from behaviour.model import SimulationModel
from runner.state import AgentState
from stopping.engine import StoppingConfig, check_stopping


def _model_at_step(step: int, states: list[dict] | None = None) -> SimulationModel:
    model = SimulationModel()
    model.step = step
    model.agents = [
        AgentState(agent_type_name="person", state=s) for s in (states or [])
    ]
    return model


def test_max_steps_reached_stops():
    model = _model_at_step(10)
    config = StoppingConfig(max_steps=10)

    result = check_stopping(model, config)

    assert result.stopped is True
    assert result.reason == "max_steps"


def test_max_steps_not_reached_continues():
    model = _model_at_step(3)
    config = StoppingConfig(max_steps=10)

    result = check_stopping(model, config)

    assert result.stopped is False
    assert result.reason is None


def test_max_steps_always_enforced_even_with_conditions_present():
    """max_steps must halt the run regardless of whether any optional
    condition would also be true or false — it's checked first,
    independent of `conditions`/`combinator`."""
    model = _model_at_step(10, [{"status": "I"}])
    config = StoppingConfig(
        max_steps=10,
        conditions=['model.count("state[\\"status\\"]==\\"Z\\"") == 99'],  # never true
    )

    result = check_stopping(model, config)

    assert result.stopped is True
    assert result.reason == "max_steps"


def test_condition_met_or_combinator():
    model = _model_at_step(1, [{"status": "I"}, {"status": "S"}])
    config = StoppingConfig(
        max_steps=100,
        conditions=[
            'model.count("state[\\"status\\"]==\\"I\\"") == 0',  # false
            'model.count("state[\\"status\\"]==\\"S\\"") == 1',  # true
        ],
        combinator="OR",
    )

    result = check_stopping(model, config)

    assert result.stopped is True
    assert result.reason == "condition_met"


def test_condition_not_met_or_combinator_continues():
    model = _model_at_step(1, [{"status": "I"}])
    config = StoppingConfig(
        max_steps=100,
        conditions=['model.count("state[\\"status\\"]==\\"S\\"") == 1'],  # false
        combinator="OR",
    )

    result = check_stopping(model, config)

    assert result.stopped is False


def test_condition_met_and_combinator_requires_all_true():
    model = _model_at_step(1, [{"status": "I"}, {"status": "I"}])
    config = StoppingConfig(
        max_steps=100,
        conditions=[
            'model.count("state[\\"status\\"]==\\"I\\"") == 2',  # true
            'model.count("state[\\"status\\"]==\\"S\\"") == 0',  # true
        ],
        combinator="AND",
    )

    result = check_stopping(model, config)

    assert result.stopped is True
    assert result.reason == "condition_met"


def test_and_combinator_one_false_continues():
    model = _model_at_step(1, [{"status": "I"}])
    config = StoppingConfig(
        max_steps=100,
        conditions=[
            'model.count("state[\\"status\\"]==\\"I\\"") == 1',  # true
            'model.count("state[\\"status\\"]==\\"S\\"") == 1',  # false
        ],
        combinator="AND",
    )

    result = check_stopping(model, config)

    assert result.stopped is False


def test_malformed_condition_is_graceful_stop_not_exception():
    model = _model_at_step(1, [{"status": "I"}])
    config = StoppingConfig(max_steps=100, conditions=["model.count( =="])

    result = check_stopping(model, config)  # must not raise

    assert result.stopped is True
    assert result.reason == "error"
    assert result.detail is not None


def test_stop_logs_event_via_model_log_event():
    model = _model_at_step(10)
    config = StoppingConfig(max_steps=10)

    check_stopping(model, config)

    assert len(model._event_log) == 1
    logged = model._event_log[0]
    assert logged["event_type"] == "simulation_stopped"


def test_no_stop_does_not_log_event():
    model = _model_at_step(3)
    config = StoppingConfig(max_steps=10)

    check_stopping(model, config)

    assert len(model._event_log) == 0