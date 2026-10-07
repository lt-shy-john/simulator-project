"""

Neighbour-aggregation helpers for expression rules (Ticket 3). Built per
call from one agent's start-of-step neighbour snapshots, so they are
topology-agnostic: AllPairs, RandomSample and Network all supply the same
list-of-AgentState shape.

"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from runner.state import AgentState


def make_neighbour_helpers(
    neighbours: Sequence[AgentState],
) -> dict[str, Callable[..., Any]]:
    """Build the five neighbour helpers bound to one neighbour snapshot.

    Mirrors the S-10 model.count/mean/sum semantics, including
    filter_expr evaluation via _evaluate_condition against each neighbour.

    Args:
        neighbours: the neighbours' AgentState snapshots for this step.

    Returns:
        Mapping of helper name to callable, ready to merge into the
        simpleeval function whitelist.
    """
    # Imported lazily, as in S-10, to avoid a circular import.
    from behaviour.condition import _evaluate_condition

    def _matching(filter_expr: str | None) -> list[AgentState]:
        if filter_expr is None:
            return list(neighbours)
        return [a for a in neighbours if _evaluate_condition(filter_expr, a)]

    def neighbor_count(filter_expr: str | None = None) -> int:
        """Number of neighbours matching filter_expr (all if None)."""
        return len(_matching(filter_expr))

    def neighbor_mean(attr: str, filter_expr: str | None = None) -> float:
        """Mean of attr over matching neighbours; 0.0 if none match.

        Unlike S-10's model.mean(), which raises ValueError on an empty set,
        this returns 0.0 so isolated agents don't abort the step.
        """
        matching = _matching(filter_expr)
        if not matching:
            return 0.0
        return sum(a.get(attr) for a in matching) / len(matching)

    def neighbor_sum(attr: str, filter_expr: str | None = None) -> float:
        """Sum of attr over matching neighbours (0 if none match)."""
        return sum(a.get(attr) for a in _matching(filter_expr))

    def neighbor_any(filter_expr: str) -> bool:
        """True if at least one neighbour matches filter_expr."""
        return neighbor_count(filter_expr) > 0

    def neighbor_all(filter_expr: str) -> bool:
        """True if every neighbour matches filter_expr (True if no neighbours)."""
        return neighbor_count(filter_expr) == len(neighbours)

    return {
        "neighbor_count": neighbor_count,
        "neighbor_mean": neighbor_mean,
        "neighbor_sum": neighbor_sum,
        "neighbor_any": neighbor_any,
        "neighbor_all": neighbor_all,
    }