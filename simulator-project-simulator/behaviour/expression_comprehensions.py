"""Comprehension support for the shared expression sandbox.

Provides AST-based hop analysis, a lazily-built neighbour namespace, and
a helper that enables comprehension nodes on a simpleeval evaluator.
Both ``neighbors`` and ``neighbours`` are accepted as name and key.
"""
from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Protocol
from collections.abc import Sized
from functools import lru_cache

from pydantic import BaseModel, Field
from simpleeval import EvalWithCompoundTypes

logger = logging.getLogger("simulator")

COMPREHENSION_NODES: tuple[type[ast.AST], ...] = (
    ast.ListComp,
    ast.GeneratorExp,
    ast.SetComp,
)
NEIGHBORS_NAMES = ("neighbors", "neighbours")
SOFT_HOP_THRESHOLD = 1  # hops beyond `neighbors` before a warning is emitted
DEFAULT_MAX_NEIGHBORS = 1000

class SandboxConfig(BaseModel):
    """Tunable limits for comprehensions in the expression sandbox.

    Attributes:
        max_neighbours: Largest neighbour set a comprehension may iterate.
        soft_hop_threshold: Hops beyond ``neighbours`` before a warning is
            logged (the expression still evaluates).
        max_hops: Optional hard cap; ``None`` means warn only.
    """

    max_neighbours: int = Field(DEFAULT_MAX_NEIGHBORS, ge=1)
    soft_hop_threshold: int = Field(SOFT_HOP_THRESHOLD, ge=0)
    max_hops: int | None = Field(None, ge=0)


_warned: set[tuple[str, int]] = set()


def reset_policy_caches() -> None:
    """Clear the analysis cache and the warned-expression set (for tests)."""
    analyse_expression.cache_clear()
    _warned.clear()


def check_neighbour_cap(
    neighbours: Sized, max_neighbours: int, *, agent_id: str | None = None
) -> None:
    """Reject a neighbour set larger than ``max_neighbours``.

    Raises:
        NeighborSetTooLargeError: if ``len(neighbours) > max_neighbours``.
    """
    if len(neighbours) > max_neighbours:
        raise NeighborSetTooLargeError(
            f"Agent {agent_id!r} has {len(neighbours)} neighbours; "
            f"comprehensions are capped at {max_neighbours}. Use a helper "
            f"such as neighbor_count(...) or raise sandbox.max_neighbours."
        )


class ComprehensionDepthError(ValueError):
    """Raised when nesting exceeds an explicitly configured hard hop cap."""


class NeighborSetTooLargeError(ValueError):
    """Raised when a neighbour set exceeds the configured size cap."""


class NeighborSource(Protocol):
    """Anything that can list neighbour IDs (assumed topology interface)."""

    def neighbors(self, agent_id: str) -> Iterable[str]: ...


@dataclass(frozen=True)
class ComprehensionReport:
    """Result of statically analysing an expression.

    Attributes:
        uses_neighbors: True if either neighbour name is referenced.
        has_comprehension: True if any comprehension node is present.
        max_hop: Deepest neighbour hop reached (0 = the neighbours name
            itself, 1 = ``n['neighbors']``, ...); -1 if none.
        warnings: Human-readable warnings, suitable for logging or a UI box.
    """

    uses_neighbors: bool
    has_comprehension: bool
    max_hop: int
    warnings: tuple[str, ...] = ()


def _target_names(target: ast.AST) -> list[str]:
    """Return all variable names bound by a comprehension target."""
    return [n.id for n in ast.walk(target) if isinstance(n, ast.Name)]


def _iter_hop(node: ast.AST, scope: Mapping[str, int]) -> int | None:
    """Return the hop level of an iterable expression, or None if it isn't
    neighbour-derived.

    ``neighbors``/``neighbours`` is hop 0; ``x['neighbors']`` where ``x`` was
    bound from a hop-k iterable is hop k+1.
    """
    if isinstance(node, ast.Name) and node.id in NEIGHBORS_NAMES and node.id not in scope:
        return 0
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        base_hop = scope.get(node.value.id)
        key = node.slice
        if (
            base_hop is not None
            and isinstance(key, ast.Constant)
            and key.value in NEIGHBORS_NAMES
        ):
            return base_hop + 1
    return None


def _max_hop(node: ast.AST, scope: Mapping[str, int]) -> int:
    """Recursively compute the deepest neighbour hop under ``node``."""
    deepest = -1
    if isinstance(node, COMPREHENSION_NODES):
        inner = dict(scope)
        for gen in node.generators:
            deepest = max(deepest, _max_hop(gen.iter, inner))
            hop = _iter_hop(gen.iter, inner)
            names = _target_names(gen.target)
            if hop is not None:
                deepest = max(deepest, hop)
                inner.update({name: hop for name in names})
            else:
                for name in names:
                    inner.pop(name, None)
            for cond in gen.ifs:
                deepest = max(deepest, _max_hop(cond, inner))
        return max(deepest, _max_hop(node.elt, inner))
    for child in ast.iter_child_nodes(node):
        deepest = max(deepest, _max_hop(child, scope))
    return deepest


@lru_cache(maxsize=1024)
def analyse_expression(expr: str) -> ComprehensionReport:
    """Statically analyse ``expr`` for comprehension use and nesting depth.

    Syntax errors yield an empty report; the evaluator will raise the real
    error with its own message.
    """
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError:
        return ComprehensionReport(False, False, -1)
    nodes = list(ast.walk(tree))
    return ComprehensionReport(
        uses_neighbors=any(
            isinstance(n, ast.Name) and n.id in NEIGHBORS_NAMES for n in nodes
        ),
        has_comprehension=any(isinstance(n, COMPREHENSION_NODES) for n in nodes),
        max_hop=_max_hop(tree, {}),
    )


def check_comprehension_policy(
    expr: str,
    *,
    soft_threshold: int = SOFT_HOP_THRESHOLD,
    max_hops: int | None = None,
) -> ComprehensionReport:
    """Analyse ``expr`` and apply the nesting policy.

    Exceeding ``soft_threshold`` records a warning on the report every time
    (so a UI box can show it) but only *logs* it once per distinct
    expression. If ``max_hops`` is set and exceeded, raises instead.

    Raises:
        ComprehensionDepthError: if ``max_hops`` is set and exceeded.
    """
    report = analyse_expression(expr)
    if max_hops is not None and report.max_hop > max_hops:
        raise ComprehensionDepthError(
            f"Expression nests {report.max_hop} hops beyond 'neighbors'; "
            f"the configured maximum is {max_hops}."
        )
    if report.max_hop > soft_threshold:
        message = (
            f"Expression nests {report.max_hop} hops beyond 'neighbors' "
            f"(soft limit {soft_threshold}); cost grows roughly with "
            f"degree^{report.max_hop + 1}."
        )
        key = (expr, soft_threshold)
        if key not in _warned:
            _warned.add(key)
            logger.warning(message)
        return ComprehensionReport(
            report.uses_neighbors, report.has_comprehension, report.max_hop, (message,)
        )
    return report


class AgentView(dict):
    """Dict snapshot of an agent's state with a lazy neighbour key.

    The neighbour list is only built (and size-checked) if the expression
    actually subscripts ``['neighbors']`` or ``['neighbours']``, so one-hop
    queries never pay for deeper hops. If an agent has a real attribute with
    one of those names it takes precedence over the lazy one.
    """

    def __init__(
        self, state: Mapping[str, Any], load_neighbors: Callable[[], list["AgentView"]]
    ) -> None:
        super().__init__(state)  # shallow copy: expression can't rebind state keys
        self._load_neighbors = load_neighbors

    def __missing__(self, key: str) -> Any:
        """Lazily build the neighbour list for either spelling of the key."""
        if key in NEIGHBORS_NAMES:
            value = self._load_neighbors()
            self[key] = value
            return value
        raise KeyError(key)


def build_neighbor_views(
    agent_id: str,
    population: Mapping[str, Any],
    topology: NeighborSource,
    *,
    max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
) -> list[AgentView]:
    """Build the neighbour iterable for ``agent_id``.

    Args:
        agent_id: The focal agent.
        population: Mapping of agent_id -> object with a ``.state`` dict
            (e.g. AgentState).
        topology: Provides ``neighbors(agent_id)``.
        max_neighbors: Cap applied to every neighbour set, at every hop.

    Raises:
        NeighborSetTooLargeError: if any neighbour set exceeds the cap.
    """

    def views_for(aid: str) -> list[AgentView]:
        ids = [i for i in topology.neighbors(aid) if i in population]
        if len(ids) > max_neighbors:
            raise NeighborSetTooLargeError(
                f"Agent {aid!r} has {len(ids)} neighbours; comprehensions are "
                f"capped at {max_neighbors}. Use a helper such as "
                f"neighbor_count(...) instead."
            )
        return [make_view(i) for i in ids]

    def make_view(aid: str) -> AgentView:
        return AgentView(population[aid].state, lambda: views_for(aid))

    return views_for(agent_id)


def enable_comprehensions(evaluator: EvalWithCompoundTypes) -> EvalWithCompoundTypes:
    """Whitelist ListComp, GeneratorExp and SetComp on ``evaluator``.

    A no-op for node types simpleeval already handles in your version.

    Raises:
        RuntimeError: if the installed simpleeval has no comprehension handler.
    """
    handler = getattr(evaluator, "_eval_comprehension", None)
    for node_type in COMPREHENSION_NODES:
        if node_type not in evaluator.nodes:
            if handler is None:
                raise RuntimeError(
                    "Installed simpleeval has no comprehension support; "
                    "check the pinned version."
                )
            evaluator.nodes[node_type] = handler
    return evaluator


def evaluate_with_neighbors(
    expr: str,
    *,
    agent_id: str,
    population: Mapping[str, Any],
    topology: NeighborSource,
    functions: Mapping[str, Callable[..., Any]] | None = None,
    max_hops: int | None = None,
    max_neighbors: int = DEFAULT_MAX_NEIGHBORS,
) -> Any:
    """Evaluate ``expr`` in the sandbox with ``state`` and the neighbour names.

    Helper functions (e.g. Ticket 3's ``neighbor_count``) are passed via
    ``functions`` and may be called inside comprehensions.
    """
    report = check_comprehension_policy(expr, max_hops=max_hops)
    names: dict[str, Any] = {"state": population[agent_id].state}
    if report.uses_neighbors:
        views = build_neighbor_views(
            agent_id, population, topology, max_neighbors=max_neighbors
        )
        for alias in NEIGHBORS_NAMES:
            names[alias] = views
    evaluator = enable_comprehensions(
        EvalWithCompoundTypes(functions=dict(functions or {}), names=names)
    )
    return evaluator.eval(expr)