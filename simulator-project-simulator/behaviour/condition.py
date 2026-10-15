"""
expression.py — Bare boolean condition evaluation for Model.count/mean (S-07).

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

from collections.abc import Callable, Iterable, Sequence
from simpleeval import EvalWithCompoundTypes, InvalidExpression
from typing import Any, Callable, Sequence

from runner.state import AgentState
from behaviour.expressions import _SAFE_FUNCTIONS
from behaviour.expression_comprehensions import (
    NEIGHBORS_NAMES,
    SandboxConfig,
    build_views_from_states,
    check_comprehension_policy,
    check_neighbour_cap,
    enable_comprehensions,
)


def _evaluate_condition(
    expr: str,
    agent: AgentState,
    neighbours: Sequence[AgentState] | None = None,
    extra_functions: dict[str, Callable[..., Any]] | None = None,
    sandbox: SandboxConfig | None = None,
    neighbours_of: Callable[[str], Iterable[AgentState]] | None = None,
) -> bool:
    """Evaluate a bare boolean condition against one agent's state.

    ...existing docstring...
        sandbox: comprehension limits; defaults to ``SandboxConfig()``.
        neighbours_of: returns the neighbours of any agent id, enabling
            ``n['neighbours']`` (one hop beyond) inside comprehensions.

    Raises:
        ValueError: ...existing reasons..., or a comprehension exceeding
            the neighbour cap or a configured hard hop cap.
    """
    sandbox = sandbox or SandboxConfig()
    report = check_comprehension_policy(
        expr,
        soft_threshold=sandbox.soft_hop_threshold,
        max_hops=sandbox.max_hops,
    )

    context: dict[str, Any] = {"state": dict(agent.state)}
    if neighbours is not None:
        if report.has_comprehension:
            check_neighbour_cap(
                neighbours, sandbox.max_neighbours,
                agent_id=getattr(agent, "agent_id", None),
            )
        if report.max_hop >= 1 and neighbours_of is not None:
            states = build_views_from_states(
                neighbours, neighbours_of, max_neighbors=sandbox.max_neighbours
            )
        else:
            states = [a.state for a in neighbours]
        for alias in NEIGHBORS_NAMES:
            context[alias] = states
    functions = {**_SAFE_FUNCTIONS, **(extra_functions or {})}

    try:
        evaluator = enable_comprehensions(
            EvalWithCompoundTypes(names=context, functions=functions)
        )
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