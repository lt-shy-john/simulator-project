from dataclasses import dataclass, field
from typing import Literal

from stopping.expression import evaluate_condition

StopReason = Literal["max_steps", "condition_met", "error"]


@dataclass
class StopResult:
    stopped: bool
    reason: StopReason | None = None
    detail: str | None = None


@dataclass
class StoppingConfig:
    max_steps: int
    conditions: list[str] = field(default_factory=list)
    combinator: Literal["AND", "OR"] = "OR"


def check_stopping(model, config: StoppingConfig) -> StopResult:
    """Called at end-of-step (model.step reflects the step just
    completed, per _reset_for_step). Checks max_steps first — always
    enforced regardless of conditions."""

    if model.step >= config.max_steps:
        result = StopResult(True, "max_steps", f"reached step {model.step}")
        _log_stop(model, result)
        return result

    if config.conditions:
        try:
            evaluated = [evaluate_condition(expr, model) for expr in config.conditions]
        except ValueError as exc:
            result = StopResult(True, "error", str(exc))
            _log_stop(model, result)
            return result

        triggered = any(evaluated) if config.combinator == "OR" else all(evaluated)
        if triggered:
            result = StopResult(True, "condition_met", f"combinator={config.combinator}")
            _log_stop(model, result)
            return result

    return StopResult(False)


def _log_stop(model, result: StopResult) -> None:
    model.log_event(
        name="simulation_stopped",
        agent_id=None,
        data={"reason": result.reason, "detail": result.detail},
    )