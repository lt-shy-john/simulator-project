"""
model.py — Model Protocol (S-05).

Scope:
  - Model: structural interface for the simulation-level context object
    passed as the third argument to BehaviourModule.apply().

Design notes:
  - Gives a behaviour module access to simulation-wide state without
    growing the apply() signature every time a new capability is added.
    A future module needing model.rng doesn't require changing every
    existing module's apply() call site.
  - This is a Protocol, not a concrete implementation, because several
    fields depend on tickets not yet built:
      - params, rng: depend on S-11 (Global Parameters / Randomness)
      - log_event: depends on S-10 (Data Collection)
    Modules can be written against this interface today. The concrete
    backing class (likely Simulation itself, from runner/simulation.py)
    will need to actually implement these once S-10/S-11 land — until
    then, a concrete Model implementation used for testing should stub
    them out explicitly (e.g. log_event as a no-op or print, rng as an
    unseeded default generator) rather than silently omitting them.
  - count() and mean() take a filter_expr string, evaluated via the same
    simpleeval-based expression evaluator built for expression fields
    (see expressions.py) — one evaluator, two use sites. filter_expr
    follows the same expression syntax as behaviour expression fields
    (e.g. "state['infected'] == True").

Not in scope here:
  - Concrete implementation — this file only declares the interface.
  - The expression evaluator itself (expressions.py, separate file).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import numpy as np

from runner.state import AgentState


@runtime_checkable
class Model(Protocol):
    """Structural interface for the simulation context object.

    Passed to every BehaviourModule.apply() call as the `model` argument.
    Gives modules access to simulation-wide state — the full population,
    current step, global parameters, shared RNG, and event logging —
    without needing any of this passed as individual apply() arguments.
    """

    step: int
    """Current step number, starting from 0 (or 1 — TBD when the executor
    is built). Lets a module conditionally activate only after a certain
    point in the simulation, e.g. `if model.step > 10: ...`."""

    agents: list[AgentState]
    """The full population, all agent types combined. NOT filtered to the
    current agent's neighbours — this is the whole simulation, for modules
    that need a broader view than their own topology provides."""

    params: dict[str, Any]
    """Global parameters (flat, time-varying, or computed). Backed by
    S-11 (Global Parameters / Randomness) — not yet implemented. A
    concrete Model used before S-11 lands should provide this as a
    plain dict populated however the caller sees fit."""

    rng: np.random.Generator
    """Shared random number generator for this simulation run. Backed by
    S-11 (Global Parameters / Randomness) — not yet implemented, seeding
    strategy TBD. A concrete Model used before S-11 lands should provide
    an explicit np.random.default_rng() instance rather than leaving
    this unset, to avoid modules silently falling back to global numpy
    random state."""

    def count(self, filter_expr: str | None = None) -> int:
        """Count agents matching filter_expr, or all agents if None.

        filter_expr is evaluated per-agent via the same simpleeval-based
        expression evaluator used for behaviour expression fields (see
        expressions.py). Example: model.count("state['infected'] == True").

        Args:
            filter_expr: a safe expression string, or None to count
                the full population

        Returns:
            number of agents matching the filter
        """
        ...

    def mean(self, attr: str, filter_expr: str | None = None) -> float:
        """Compute the mean of attr across agents, optionally filtered.

        Args:
            attr: the attribute name to average
            filter_expr: a safe expression string restricting which
                agents are included, or None for the full population

        Returns:
            the mean value of attr across matching agents

        Raises:
            KeyError: if attr is not a defined attribute
            ValueError: if no agents match filter_expr (mean of empty set)
        """
        ...

    def log_event(self, name: str, agent_id: str, data: dict[str, Any] | None = None) -> None:
        """Record a named event for later analysis.

        Backed by S-10 (Data Collection) — not yet implemented. A concrete
        Model used before S-10 lands should provide an explicit stub
        (no-op, print, or in-memory list) rather than silently discarding
        calls, so module authors get some signal during development that
        events aren't actually being persisted yet.

        Args:
            name: event name/category, e.g. "infection", "trade"
            agent_id: the agent this event pertains to
            data: optional additional event data
        """