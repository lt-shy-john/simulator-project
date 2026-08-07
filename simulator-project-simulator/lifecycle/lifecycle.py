"""
lifecycle.py — Agent Lifecycle (S-07).

Scope:
  - Pending event dataclasses (ReproduceEvent, RemoveEvent,
    ExternalEntryEvent) — queued during a step, never applied immediately.
  - apply_pending_lifecycle_events: drains the queue once at step-end,
    mirroring accessor.py's apply_deferred_writes pattern exactly, per
    the ticket's own note ("add to a pending queue and process at end of
    step to avoid mid-step list mutation bugs").

Design notes:
  - All three actions (reproduce, remove, external_entry) are ONLY
    triggered from inside a BehaviourModule's apply(), via model.reproduce(),
    model.remove(), model.external_entry() — see model.py. Expressions
    cannot trigger any of these; evaluate_expression() never receives
    `model` at all (see expressions.py), so there is no path from an
    expression string to a lifecycle event.
  - Condition-based and probabilistic removal (two of the ticket's
    acceptance criteria) are NOT separate mechanisms — they're just
    common patterns a module author writes themselves using ordinary
    Python (an if-check, a random.random() roll) before calling
    model.remove(agent_id). No dedicated "remove_if" or
    "remove_with_probability" helper is provided; model.remove() is the
    only primitive, by design (researcher's own call — Option A).
  - reproduce() supports per-attribute inherit-vs-fresh sampling.
    Default is INHERIT for every attribute unless the caller explicitly
    marks specific attributes as "fresh". This mirrors genetic-algorithm-
    style inheritance-with-mutation, per researcher's framing — fresh
    attributes are sampled the same way initialise_population (S-02)
    samples a brand-new agent's attributes, using that AttributeDefinition's
    distribution.
  - external_entry() has NO parent — every attribute is always freshly
    sampled, same as ordinary population initialisation. There is no
    inherit option for external entry, since there's no agent to inherit
    from.
  - Agent IDs for both reproduce and external_entry use the same
    str(uuid.uuid4()) default AgentState already uses — this satisfies
    "agent IDs are unique and never reused" for free, since nothing here
    invents a different ID scheme.
  - Births/deaths event logging (ticket criterion, "see S-13") is NOT
    implemented here — depends on S-10 (Data Collection) / whatever S-13
    turns out to be, same placeholder pattern as model.log_event.

Not in scope here:
  - The concrete Model implementation that actually appends to this
    queue when model.reproduce/remove/external_entry are called — Model
    is still a bare Protocol (see model.py). Wiring a concrete Model
    class that holds a reference to this queue, plus the AgentType
    registry needed for fresh-sampling, is follow-up work for
    executor.py, not done in this file.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from runner.state import AgentState, _sample_distribution
from agents.agents import AgentType


# ---------------------------------------------------------------------------
# Pending event types
# ---------------------------------------------------------------------------

@dataclass
class ReproduceEvent:
    """Queued by model.reproduce(). Processed at step-end."""
    agent_type: str
    parent_id: str
    fresh_attributes: list[str] = field(default_factory=list)
    """Attribute names to freshly sample rather than inherit from the
    parent. Any attribute NOT in this list is inherited (copied exactly
    from the parent's current value) — this is the default behaviour."""


@dataclass
class RemoveEvent:
    """Queued by model.remove(). Processed at step-end."""
    agent_id: str


@dataclass
class ExternalEntryEvent:
    """Queued by model.external_entry(). Processed at step-end.
    Always freshly samples every attribute — no parent, no inherit option.
    """
    agent_type: str
    count: int


LifecycleEvent = ReproduceEvent | RemoveEvent | ExternalEntryEvent


# ---------------------------------------------------------------------------
# Step-end processing
# ---------------------------------------------------------------------------

def apply_pending_lifecycle_events(
    live_population: dict[str, AgentState],
    pending_events: list[LifecycleEvent],
    agent_types: dict[str, AgentType],
    rng: np.random.Generator,
) -> None:
    """Drain the pending lifecycle event queue, mutating live_population
    in place. Called once by the executor after all agents have been
    processed for this step — mirrors apply_deferred_writes exactly.

    Events are applied in the order they were queued. A RemoveEvent for
    an agent_id already removed by an earlier event in the same queue
    (e.g. queued twice by two different modules) is treated as a no-op
    rather than an error — the end state (agent gone) is the same either
    way, and raising here would make queue ordering fragile for no
    real benefit.

    Args:
        live_population: agent_id -> AgentState, mutated in place —
            new agents are added, removed agents are deleted
        pending_events: the queue populated during this step via
            model.reproduce() / model.remove() / model.external_entry()
        agent_types: agent_type_name -> AgentType, needed to look up
            AttributeDefinitions for fresh-sampling (reproduce's fresh
            attributes, and all of external_entry's attributes)
        rng: shared seeded generator (typically model.rng) used for all
            fresh-attribute sampling in this call — same generator the
            rest of the simulation draws from, so reproduce()/
            external_entry() stay reproducible under a fixed seed.

    Raises:
        KeyError: if a ReproduceEvent's parent_id is not found in
            live_population, or if agent_type is not found in agent_types
    """
    for event in pending_events:
        if isinstance(event, ReproduceEvent):
            _apply_reproduce(event, live_population, agent_types, rng)
        elif isinstance(event, RemoveEvent):
            live_population.pop(event.agent_id, None)  # no-op if already gone
        elif isinstance(event, ExternalEntryEvent):
            _apply_external_entry(event, live_population, agent_types, rng)
        else:
            raise ValueError(f"Unknown lifecycle event type: {type(event)}")


def _apply_reproduce(
    event: ReproduceEvent,
    live_population: dict[str, AgentState],
    agent_types: dict[str, AgentType],
    rng: np.random.Generator,
) -> None:
    """Create a new agent from a ReproduceEvent, inheriting or freshly
    sampling each attribute per event.fresh_attributes."""
    if event.parent_id not in live_population:
        raise KeyError(
            f"Cannot reproduce: parent_id '{event.parent_id}' not found "
            f"in live population."
        )
    if event.agent_type not in agent_types:
        raise KeyError(
            f"Cannot reproduce: agent_type '{event.agent_type}' not found "
            f"in agent_types."
        )

    parent = live_population[event.parent_id]
    agent_type_def = agent_types[event.agent_type]

    child_state: dict[str, Any] = {}
    for attr in agent_type_def.attributes:
        if attr.name in event.fresh_attributes and attr.distribution is not None:
            # Fresh sample — same distribution logic as initial population.
            sampled_array = _sample_distribution(attr, count=1, rng=rng)
            value = sampled_array[0]
            child_state[attr.name] = value.item() if hasattr(value, "item") else value
        else:
            # Inherit — default. Copy parent's current value exactly.
            child_state[attr.name] = parent.state.get(attr.name)

    child = AgentState(
        agent_id=str(uuid.uuid4()),
        agent_type_name=event.agent_type,
        state=child_state,
    )
    live_population[child.agent_id] = child


def _apply_external_entry(
    event: ExternalEntryEvent,
    live_population: dict[str, AgentState],
    agent_types: dict[str, AgentType],
    rng: np.random.Generator,
) -> None:
    """Add `count` freshly-sampled new agents of the given type. No
    parent — every attribute is sampled fresh, same as initial population
    generation."""
    if event.agent_type not in agent_types:
        raise KeyError(
            f"Cannot process external entry: agent_type '{event.agent_type}' "
            f"not found in agent_types."
        )

    agent_type_def = agent_types[event.agent_type]

    for _ in range(event.count):
        new_state: dict[str, Any] = {}
        for attr in agent_type_def.attributes:
            if attr.distribution is not None:
                sampled_array = _sample_distribution(attr, count=1, rng=rng)
                value = sampled_array[0]
                new_state[attr.name] = value.item() if hasattr(value, "item") else value
            else:
                new_state[attr.name] = None  # schema-only attribute, no distribution yet

        new_agent = AgentState(
            agent_id=str(uuid.uuid4()),
            agent_type_name=event.agent_type,
            state=new_state,
        )
        live_population[new_agent.agent_id] = new_agent