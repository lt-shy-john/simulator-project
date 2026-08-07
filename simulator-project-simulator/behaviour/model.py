"""
model.py — Model Protocol (S-05, updated for S-07 Agent Lifecycle).

Scope:
  - Model: structural interface for the simulation-level context object
    passed as the third argument to BehaviourModule.apply().

Design notes:
  - step, agents, params, rng, count(), mean(), log_event(): see original
    S-05 notes below — params/rng/log_event still depend on S-11/S-10,
    not yet implemented.
  - UPDATED (S-07): reproduce(), remove(), external_entry() added.
    These are the ONLY way a behaviour module can create or destroy
    agents — expressions have no access to model at all (see
    expressions.py), so lifecycle actions can only originate from a
    module's apply(). None of these three act immediately: they queue a
    LifecycleEvent (see lifecycle.py) that is only applied at step-end,
    per the ticket's explicit note about avoiding mid-step list mutation
    bugs. A concrete Model implementation must hold a reference to that
    step's pending event queue and append to it — this Protocol only
    declares the call signature, not the queuing mechanism itself.
  - Condition-based and probabilistic removal (ticket acceptance
    criteria) are NOT separate methods — a module author writes the
    condition or probability check themselves in plain Python, then
    calls remove() if it's true. No remove_if()/remove_with_probability()
    convenience wrapper is provided, by design.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import numpy as np

from runner.state import AgentState


@runtime_checkable
class Model(Protocol):
    """Structural interface for the simulation context object.

    Passed to every BehaviourModule.apply() call as the `model` argument.
    """

    step: int
    """Current step number. Also the mechanism a module uses to implement
    external_entry's "configurable step interval" itself — e.g.
    `if model.step % 10 == 0: model.external_entry(...)`. There is no
    separate interval-checking mechanism; the module author checks
    model.step directly."""

    agents: list[AgentState]
    """The full population, all agent types combined."""

    params: dict[str, Any]
    """Global parameters. Backed by S-11 — not yet implemented."""

    rng: np.random.Generator
    """Shared random number generator. Backed by S-11 — not yet implemented."""

    def count(self, filter_expr: str | None = None) -> int:
        """Count agents matching filter_expr, or all agents if None."""
        ...

    def mean(self, attr: str, filter_expr: str | None = None) -> float:
        """Compute the mean of attr across agents, optionally filtered."""
        ...

    def log_event(self, name: str, agent_id: str, data: dict[str, Any] | None = None) -> None:
        """Record a named event for later analysis. Backed by S-10 —
        not yet implemented."""
        ...

    def reproduce(
        self,
        agent_type: str,
        parent_id: str,
        fresh_attributes: list[str] | None = None,
    ) -> None:
        """Queue creation of a new agent of `agent_type`, inheriting from
        the agent identified by `parent_id`.

        Does NOT create the agent immediately — queues a ReproduceEvent
        (see lifecycle.py) applied at step-end.

        By default every attribute is INHERITED — the child's value is
        copied exactly from the parent's current value. Pass attribute
        names in fresh_attributes to freshly sample those specific
        attributes instead (from that AttributeDefinition's distribution),
        same as a brand-new agent would be sampled at population
        initialisation. This is inheritance-with-mutation, similar in
        spirit to a genetic algorithm's offspring generation, though this
        platform does not implement selection/fitness/crossover itself —
        only the inherit-vs-fresh sampling primitive.

        Args:
            agent_type: the AgentType name for the new agent
            parent_id: the agent_id to inherit attribute values from
            fresh_attributes: attribute names to freshly sample instead
                of inheriting. None or empty list means inherit everything.
        """
        ...

    def remove(self, agent_id: str) -> None:
        """Queue removal of the given agent.

        Does NOT remove the agent immediately — queues a RemoveEvent
        applied at step-end. This is the only removal primitive; there
        is no separate condition-based or probabilistic removal method.
        A module author implements those patterns themselves:

            if agent.get("health") <= 0:
                model.remove(agent.agent_id)

            if random.random() < 0.05:
                model.remove(agent.agent_id)

        Args:
            agent_id: the agent to remove
        """

    def external_entry(self, agent_type: str, count: int) -> None:
        """Queue creation of `count` new agents of `agent_type`, with no
        parent — every attribute is freshly sampled, same as initial
        population generation. There is no inherit option here, since
        there's nothing to inherit from.

        Does NOT create the agents immediately — queues an
        ExternalEntryEvent applied at step-end.

        A module author implements the "configurable step interval" from
        the ticket themselves, using model.step:

            if model.step % 10 == 0:
                model.external_entry("person", count=5)

        Args:
            agent_type: the AgentType name for the new agents
            count: how many agents to add
        """


# ---------------------------------------------------------------------------
# Concrete implementation
# ---------------------------------------------------------------------------

class SimulationModel:
    """Concrete implementation of the Model Protocol.

    LIFETIME: one SimulationModel instance persists across the WHOLE
    simulation run — it is built once before the step loop starts, not
    rebuilt every step. This matters for fields like `rng` that must
    stay the same object across steps (rebuilding would risk accidentally
    losing RNG state between steps).

    Step-scoped fields (pending_events) are reset via _reset_for_step(),
    called by executor.py's run_step once at the start of each step —
    NOT by constructing a new SimulationModel each time.

    params, rng, and log_event's actual event storage are stubbed here
    (plain dict, unseeded default RNG, no-op append) since S-10/S-11
    don't exist yet — replace these internals once those tickets land,
    without needing to change this class's public interface.
    """

    def __init__(self, params: dict[str, Any] | None = None, seed: int | None = None):
        self.step: int = 0
        self.agents: list[AgentState] = []
        self.params: dict[str, Any] = params or {}
        self.rng: np.random.Generator = np.random.default_rng(seed)

        # Step-scoped — reset every step via _reset_for_step, never
        # persists across steps.
        self._pending_events: list = []

        # Stub event log — S-10 will replace this with real persistence.
        self._event_log: list[dict[str, Any]] = []

    def _reset_for_step(self, step_number: int, live_population: dict[str, AgentState]) -> None:
        """Called by run_step once at the start of each step. Updates
        step-scoped fields; does NOT touch run-scoped fields like rng."""
        self.step = step_number
        self.agents = list(live_population.values())
        self._pending_events = []

    def count(self, filter_expr: str | None = None) -> int:
        if filter_expr is None:
            return len(self.agents)
        from behaviour.condition import _evaluate_condition
        return sum(1 for a in self.agents if _evaluate_condition(filter_expr, a))

    def mean(self, attr: str, filter_expr: str | None = None) -> float:
        matching = self.agents
        if filter_expr is not None:
            from behaviour.condition import _evaluate_condition
            matching = [a for a in self.agents if _evaluate_condition(filter_expr, a)]
        if not matching:
            raise ValueError(f"mean(): no agents match filter_expr {filter_expr!r}")
        return sum(a.get(attr) for a in matching) / len(matching)

    def sum(self, attr: str, filter_expr: str | None = None) -> float:
        matching = self.agents
        if filter_expr is not None:
            from behaviour.condition import _evaluate_condition
            matching = [a for a in self.agents if _evaluate_condition(filter_expr, a)]
        return sum(a.get(attr) for a in matching)

    def log_event(self, name: str, agent_id: str, data: dict[str, Any] | None = None) -> None:
        # Stub — S-10 replaces this with real persistence.
        self._event_log.append({"name": name, "agent_id": agent_id, "data": data, "step": self.step})

    def reproduce(
        self,
        agent_type: str,
        parent_id: str,
        fresh_attributes: list[str] | None = None,
    ) -> None:
        from lifecycle.lifecycle import ReproduceEvent
        self._pending_events.append(ReproduceEvent(
            agent_type=agent_type,
            parent_id=parent_id,
            fresh_attributes=fresh_attributes or [],
        ))

    def remove(self, agent_id: str) -> None:
        from lifecycle.lifecycle import RemoveEvent
        self._pending_events.append(RemoveEvent(agent_id=agent_id))

    def external_entry(self, agent_type: str, count: int) -> None:
        from lifecycle.lifecycle import ExternalEntryEvent
        self._pending_events.append(ExternalEntryEvent(agent_type=agent_type, count=count))