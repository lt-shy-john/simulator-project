from simpleeval import EvalWithCompoundTypes, InvalidExpression


class _ConditionModelProxy:
    """Restricted view of SimulationModel exposed to S-10 condition
    expressions. Only count/mean/sum are public. Passing the real
    SimulationModel here would let a condition string reach
    model.log_event(...), model.agents, model.remove(...), etc. — this
    proxy exists purely to cap the reachable surface to the three
    aggregates the S-10 ticket names as safe."""

    def __init__(self, model):
        self._model = model

    def count(self, filter_expr: str | None = None) -> int:
        return self._model.count(filter_expr)

    def mean(self, attr: str, filter_expr: str | None = None) -> float:
        return self._model.mean(attr, filter_expr)

    def sum(self, attr: str, filter_expr: str | None = None) -> float:
        return self._model.sum(attr, filter_expr)


def evaluate_condition(expr: str, model) -> bool:
    """Evaluate one S-10 condition expression against model-level
    aggregates, e.g. 'model.count("status==I") == 0'.

    Raises:
        ValueError: unsafe/malformed expression, or result isn't bool —
        same contract as behaviour.condition._evaluate_condition.
    """
    context = {"model": _ConditionModelProxy(model)}
    try:
        evaluator = EvalWithCompoundTypes(names=context)
        result = evaluator.eval(expr)
    except InvalidExpression as e:
        raise ValueError(f"Condition '{expr}' failed to evaluate safely: {e}") from e
    except (SyntaxError, TypeError, NameError) as e:
        raise ValueError(f"Condition '{expr}' failed to evaluate: {e}") from e

    if not isinstance(result, bool):
        raise ValueError(
            f"Condition '{expr}' did not evaluate to a boolean (got "
            f"{type(result).__name__}: {result!r})."
        )
    return result