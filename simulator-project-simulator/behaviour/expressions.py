"""
Safe expression evaluation for expression fields (S-05).

Scope:
  - evaluate_expression: parses and safely executes a single assignment-
    style expression string against an agent's own state, e.g.
    'state["energy"] -= 1'. Legacy single-string form, kept as is.
  - evaluate_step / run_rule_steps: execute a list of steps (plain
    {field, expression, topology_name?} assignments and nested
    {condition, then, else} conditionals) built by behaviour.rule_steps.
    Steps carry PURE expressions (e.g. 'state["age"] + 1'); the write is
    done here, since simpleeval only evaluates expressions.
  - Read-only access to neighbour state is available inside expressions
    via a precomputed `neighbours` list — see below.
  - The same underlying safe-eval machinery backs Model.count() and
    Model.mean() (see model.py) for their filter_expr argument.

Design notes:
  - simpleeval evaluates EXPRESSIONS, not statements. The legacy path
    parses 'state["energy"] -= 1' with a regex into (key, operator, rhs),
    evaluates rhs with simpleeval, then applies the operator manually.
    The step path gets the same effect by desugaring statements into
    {field, expression} pairs at config-build time (rule_steps.desugar_line).
  - Only the current agent's own state can ever be written. Neighbour-
    affecting logic belongs in a BehaviourModule using NeighbourAccessor
    (accessor.py), so write_mode enforcement cannot be bypassed.
  - Sequential semantics (own state): every step's write is applied
    immediately via agent.set(), and each evaluation takes a fresh copy of
    agent.state, so later steps see earlier writes — same as native Python.
  - Snapshot semantics (neighbour reads): `neighbours` is precomputed by
    the executor from start-of-step state (strict t-1, same guarantee as
    NeighbourAccessor.read()). For steps, the executor supplies a
    `neighbours_for(topology_name)` lookup into that same snapshot.
  - NEVER uses raw eval() or exec() — simpleeval only, per ticket notes.

Not in scope here:
  - Multi-statement strings in the legacy path — one string = one
    assignment. Multiple assignments are expressed as multiple steps.
  - Assignment to anything other than state[...].
  - Config-time validation (topology_name rules, nesting warning): see
    behaviour/rule_steps.py.
"""

from __future__ import annotations

import re
from typing import Any, Callable

import ast
from functools import lru_cache
from simpleeval import EvalWithCompoundTypes, InvalidExpression

from behaviour.expression_steps import NEIGHBOUR_HELPERS, AssignmentStep, ConditionalRule, RuleStep
from behaviour.neighbour_helpers import make_neighbour_helpers
from runner.state import AgentState


# Functions explicitly whitelisted for use inside expressions. simpleeval
# does not expose any builtins by default — anything used inside an
# expression (e.g. any(), sum()) must be listed here explicitly. Keep this
# list deliberately small; it is the actual security boundary for what
# expression fields can do. Ticket 3's neighbour helpers (neighbor_count,
# neighbor_mean, ...) are passed in per call via `extra_functions`, because
# they are bound to the current step's snapshot.
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

# Returns the start-of-step neighbour snapshots for a topology.
NeighboursFor = Callable[[str | None], list[AgentState]]


def _safe_eval(
    expression: str,
    agent: AgentState,
    neighbours_state: list[dict[str, Any]],
    extra_functions: dict[str, Callable[..., Any]] | None = None,
    display: str | None = None,
) -> Any:
    """Evaluate one pure expression with simpleeval and return its value.

    Args:
        expression: the expression to evaluate, e.g. 'state["age"] + 1'.
        agent: supplies `state` (a fresh copy, so expressions can't mutate it).
        neighbours_state: read-only list of neighbour state dicts (t-1).
        extra_functions: additional whitelisted callables, e.g. the
            snapshot-bound neighbour helpers from Ticket 3.
        display: text used in error messages (defaults to `expression`);
            lets the legacy path keep reporting the full original string.

    Raises:
        ValueError: on any unsafe, undefined or syntactically invalid
            expression, so callers never see simpleeval's own exceptions.
    """
    shown = display if display is not None else expression
    context = {
        "state": dict(agent.state),
        "neighbours": neighbours_state,
    }
    functions = {**_SAFE_FUNCTIONS, **(extra_functions or {})}

    try:
        evaluator = EvalWithCompoundTypes(names=context, functions=functions)
        return evaluator.eval(expression)
    except InvalidExpression as e:
        raise ValueError(f"Expression '{shown}' failed to evaluate safely: {e}") from e
    except (SyntaxError, NameError) as e:
        raise ValueError(f"Expression '{shown}' failed to evaluate: {e}") from e


def evaluate_expression(
    expr: str,
    agent: AgentState,
    neighbours_state: list[dict[str, Any]],
) -> None:
    """Parse and execute one assignment-style expression against agent.state.

    Legacy single-string form. Mutates agent.state in place. Always a
    self-write — expressions cannot target neighbour state (see module
    docstring). Reading neighbour state is allowed via the `neighbours`
    name inside the expression.

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
            operations, syntax errors).
        KeyError: if the target key is not a defined attribute on agent
            (raised by AgentState.get/set — see runner/state.py). This
            applies to '=' as well, consistent with S-02's design that new
            attributes cannot be added to an agent's state at runtime.
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
    rhs_value = _safe_eval(
        match.group("rhs"), agent, neighbours_state, display=expr
    )

    current_value = agent.get(key) if op != "=" else None
    try:
        new_value = _SUPPORTED_OPS[op](current_value, rhs_value)
    except (ZeroDivisionError, TypeError) as e:
        raise ValueError(f"Expression '{expr}' failed to apply: {e}") from e
    agent.set(key, new_value)


def evaluate_step(
    step: AssignmentStep,
    agent: AgentState,
    neighbours_for: NeighboursFor,
) -> None:
    """Evaluate one plain step and write the result to agent.state[field].

    Args:
        step: the validated AssignmentStep.
        agent: the AgentState being mutated.
        neighbours_for: resolves topology_name to neighbour AgentState
            snapshots (start-of-step).

    Raises:
        ValueError: if the expression fails to evaluate safely.
        KeyError: if step.field is not defined on the agent.
    """
    neighbour_agents = neighbours_for(step.topology_name)
    value = _safe_eval(
        step.expression,
        agent,
        [a.state for a in neighbour_agents],
        make_neighbour_helpers(neighbour_agents),
    )
    agent.set(step.field, value)


@lru_cache(maxsize=1024)
def _uses_neighbours(expression: str) -> bool:
    """True if the expression calls a neighbour helper or reads `neighbours`.

    Cached, so conditions that only read own state skip building the
    neighbour list (which is O(N) under AllPairs).
    """
    return any(
        (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id in NEIGHBOUR_HELPERS
        )
        or (isinstance(n, ast.Name) and n.id == "neighbours")
        for n in ast.walk(ast.parse(expression, mode="eval"))
    )


def run_rule_steps(
    steps: list[RuleStep],
    agent: AgentState,
    neighbours_for: NeighboursFor,
) -> None:
    """Run a rule's steps in order against one agent.

    Conditions are evaluated at the point they are reached, so they see
    writes made by earlier steps. Conditions may call the neighbour
    helpers; they resolve neighbours through the conditional's own
    topology_name. Iterative, so nesting depth has no hard cap.

    Args:
        steps: AssignmentStep / ConditionalRule list from build_rule_steps.
        agent: the AgentState being mutated.
        neighbours_for: resolves topology_name to start-of-step neighbour
            AgentState snapshots.
    """
    from behaviour.condition import _evaluate_condition  # lazy, as in S-10

    stack = [iter(steps)]
    while stack:
        step = next(stack[-1], None)
        if step is None:
            stack.pop()
        elif isinstance(step, ConditionalRule):
            if _uses_neighbours(step.condition):
                neighbour_agents = neighbours_for(step.topology_name)
                taken = _evaluate_condition(
                    step.condition,
                    agent,
                    neighbour_agents,
                    make_neighbour_helpers(neighbour_agents),
                )
            else:
                taken = _evaluate_condition(step.condition, agent)
            stack.append(iter(step.then if taken else step.else_))
        else:
            evaluate_step(step, agent, neighbours_for)