"""
expressions.py — Safe expression evaluation for expression fields (S-05).

Scope:
  - evaluate_expression: parses and safely executes a single assignment-
    style expression string against an agent's own state, e.g.
    'state["energy"] -= 1'.
  - Read-only access to neighbour state is available inside expressions
    via a precomputed `neighbours` list — see below.
  - The same underlying safe-eval machinery backs Model.count() and
    Model.mean() (see model.py) for their filter_expr argument.

Design notes:
  - simpleeval evaluates EXPRESSIONS, not statements. 'state["energy"] -= 1'
    is an augmented assignment statement, which simpleeval cannot run
    directly. This module parses the string into (target_key, operator,
    rhs_expression) using a regex, evaluates rhs_expression with
    simpleeval, then applies the operator manually. Only 'state[...]'
    is a valid assignment target — expressions can only ever mutate the
    current agent's own state, never a neighbour's. Neighbour-affecting
    logic belongs in a BehaviourModule using NeighbourAccessor (accessor.py),
    not an expression field. This keeps write_mode enforcement intact —
    expressions have no mechanism to bypass it, because they cannot write
    to neighbours at all.
  - Reading neighbour state IS allowed inside the rhs expression, via a
    `neighbours` name bound to a list of read-only dicts — one dict per
    neighbour, containing that neighbour's full state as of the start of
    this step (strict t-1, same guarantee as NeighbourAccessor.read()).
    Example: 'state["infected"] = any(n["infected"] for n in neighbours)'
  - NEVER uses raw eval() or exec() — simpleeval only, per ticket notes.

Not in scope here:
  - Multi-statement expressions (e.g. two assignments in one string) —
    one expression field = one assignment, always.
  - Assignment to attributes other than via state[...] — no support for
    bare attribute access, function calls as targets, etc.
"""

from __future__ import annotations

import re
from typing import Any

from simpleeval import EvalWithCompoundTypes, InvalidExpression

from runner.state import AgentState


# Functions explicitly whitelisted for use inside expressions. simpleeval
# does not expose any builtins by default — anything used inside an
# expression (e.g. any(), sum()) must be listed here explicitly. Keep this
# list deliberately small; it is the actual security boundary for what
# expression fields can do.
_SAFE_FUNCTIONS = {
    "any": any,
    "all": all,
    "sum": sum,
    "len": len,
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
}


# Matches: state["key"] OP rest_of_expression
# OP is one of: =, +=, -=, *=, /=
# Captures: key (quoted string), operator, rhs (everything after operator)
_ASSIGNMENT_PATTERN = re.compile(
    r'^\s*state\[(["\'])(?P<key>\w+)\1\]\s*(?P<op>=|\+=|-=|\*=|/=)\s*(?P<rhs>.+)$'
)

_SUPPORTED_OPS = {
    "=": lambda current, rhs: rhs,
    "+=": lambda current, rhs: current + rhs,
    "-=": lambda current, rhs: current - rhs,
    "*=": lambda current, rhs: current * rhs,
    "/=": lambda current, rhs: current / rhs,
}


def evaluate_expression(
    expr: str,
    agent: AgentState,
    neighbours_state: list[dict[str, Any]],
) -> None:
    """Parse and execute one assignment-style expression against agent.state.

    Mutates agent.state in place. Always a self-write — expressions cannot
    target neighbour state (see module docstring). Reading neighbour state
    is allowed via the `neighbours` name inside the expression.

    Args:
        expr: the expression string, e.g. 'state["energy"] -= 1' or
              'state["infected"] = any(n["infected"] for n in neighbours)'
        agent: the AgentState being mutated
        neighbours_state: read-only list of dicts, one per neighbour,
            each containing that neighbour's state as of the start of
            this step. Precomputed by the executor before calling this
            function — same t-1 guarantee as NeighbourAccessor.read().

    Raises:
        ValueError: if expr doesn't match the required
            'state["key"] OP expression' shape, or if the rhs expression
            fails to evaluate safely (undefined names, disallowed
            operations, syntax errors — all wrapped as ValueError so
            callers don't need to know about simpleeval's own exception
            types).
        KeyError: if the target key is not a defined attribute on agent
            (raised by AgentState.get/set — see runner/state.py), except
            for '=' assignment where the key does not need to already
            exist... NOTE: current AgentState.set() requires the key to
            already exist for ALL operators including '=', consistent
            with S-02's design that new attributes cannot be added to an
            agent's state at runtime. This means an expression field
            cannot introduce a brand-new attribute — it can only update
            one already defined on the agent type in S-01/S-02.
    """
    match = _ASSIGNMENT_PATTERN.match(expr)
    if not match:
        raise ValueError(
            f"Expression '{expr}' does not match the required shape "
            f"'state[\"key\"] OP expression', where OP is one of "
            f"{sorted(_SUPPORTED_OPS.keys())}."
        )

    key = match.group("key")
    op = match.group("op")
    rhs_expr = match.group("rhs")

    # Build the safe evaluation context. `state` gives read access to the
    # agent's own current values (needed for e.g. 'state["x"] = state["y"] + 1').
    # `neighbours` gives read-only access to neighbour state, precomputed
    # by the executor as plain dicts (not AgentState objects — no risk of
    # a clever expression finding a way to call .set() on them).
    context = {
        "state": dict(agent.state),  # read-only copy, expressions can't mutate via this
        "neighbours": neighbours_state,
    }

    try:
        evaluator = EvalWithCompoundTypes(names=context, functions=_SAFE_FUNCTIONS)
        rhs_value = evaluator.eval(rhs_expr)
    except InvalidExpression as e:
        raise ValueError(
            f"Expression '{expr}' failed to evaluate safely: {e}"
        ) from e
    except (SyntaxError, NameError) as e:
        raise ValueError(
            f"Expression '{expr}' failed to evaluate: {e}"
        ) from e

    current_value = agent.get(key) if op != "=" else None
    try:
        new_value = _SUPPORTED_OPS[op](current_value, rhs_value)
    except (ZeroDivisionError, TypeError) as e:
        raise ValueError(f"Expression '{expr}' failed to apply: {e}") from e
    agent.set(key, new_value)
    new_value = _SUPPORTED_OPS[op](current_value, rhs_value)
    agent.set(key, new_value)