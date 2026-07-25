"""
condition.py — Bare boolean condition evaluation for Model.count/mean (S-07).

Scope:
  - _evaluate_condition: evaluates a bare expression (e.g.
    "state['infected'] == True") against a single agent, returning a
    bool. Used internally by SimulationModel.count() and .mean() (see
    model.py) to filter the population — NOT used by evaluate_expression
    in expressions.py, which handles assignment-shaped strings only.

Design notes:
  - This is a SEPARATE function from evaluate_expression, not a variant
    of it. evaluate_expression parses out an assignment target
    ('state["key"] OP rhs') and mutates agent.state. A condition string
    has no assignment at all — it's just a boolean expression evaluated
    directly, with no mutation. Reusing evaluate_expression's regex-based
    assignment parsing would be wrong here since there's no 'state["key"]
    = ...' shape to match against.
  - Uses the exact same simpleeval sandbox (_SAFE_FUNCTIONS, no raw
    eval()) as evaluate_expression, for the same safety guarantees.
  - Only has access to `state` (the agent being tested) — no `neighbours`
    context, since Model.count/mean operate over the whole population,
    not a specific agent's neighbour list. If neighbour-aware filtering
    is ever needed here, this would need extending — not required by
    the current ticket.
"""

from __future__ import annotations

from simpleeval import EvalWithCompoundTypes, InvalidExpression

from runner.state import AgentState
from behaviour.expressions import _SAFE_FUNCTIONS


def _evaluate_condition(expr: str, agent: AgentState) -> bool:
    """Evaluate a bare boolean condition against one agent's state.

    Args:
        expr: a safe expression string, e.g. "state['infected'] == True"
            or "state['energy'] > 10". No assignment — this is a pure
            boolean test, nothing is mutated.
        agent: the agent to test the condition against

    Returns:
        the boolean result of evaluating expr

    Raises:
        ValueError: if expr fails to evaluate safely (undefined names,
            disallowed operations, syntax errors), or if the result
            isn't a bool
    """
    context = {"state": dict(agent.state)}

    try:
        evaluator = EvalWithCompoundTypes(names=context, functions=_SAFE_FUNCTIONS)
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