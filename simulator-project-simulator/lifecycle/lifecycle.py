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
) -> list[dict[str, Any]]:
    """Drain the pending lifecycle event queue, mutating live_population
    in place, and return a list of event records describing what was
    applied - for the caller (run_step) to feed into model.log_event().

    This function has no reference to `model` by design: it reports what
    happened rather than logging it directly, so S-07's lifecycle logic
    doesn't take on a dependency on the Event Log's existence.

    A RemoveEvent for an agent_id already removed by an earlier event in
    the same queue is still a no-op for population state, but is not
    logged as agent_removed - since the agent wasn't actually removed by
    this call, logging it would misrepresent what happened this step.

    Returns:
        List of dicts shaped like {"event_type": str, "agent_id": str |
        None, "data": dict}. "agent_id" is None for ExternalEntryEvent,
        which creates multiple agents in one batch (ids are in
        data["agent_ids"] instead).
    """
    logged_events: list[dict[str, Any]] = []

    for event in pending_events:
        if isinstance(event, ReproduceEvent):
            new_agent_id = _apply_reproduce(event, live_population, agent_types, rng)
            logged_events.append({
                "event_type": "agent_created",
                "agent_id": new_agent_id,
                "data": {"via": "reproduction", "parent_id": event.parent_id},
            })
        elif isinstance(event, RemoveEvent):
            existed = event.agent_id in live_population
            live_population.pop(event.agent_id, None)
            if existed:
                logged_events.append({
                    "event_type": "agent_removed",
                    "agent_id": event.agent_id,
                    "data": {},
                })
        elif isinstance(event, ExternalEntryEvent):
            new_agent_ids = _apply_external_entry(event, live_population, agent_types, rng)
            logged_events.append({
                "event_type": "agent_created",
                "agent_id": None,
                "data": {"via": "external_entry", "count": event.count, "agent_ids": new_agent_ids},
            })
        else:
            raise ValueError(f"Unknown lifecycle event type: {type(event)}")

    return logged_events

def _apply_reproduce(
    event: ReproduceEvent,
    live_population: dict[str, AgentState],
    agent_types: dict[str, AgentType],
    rng: np.random.Generator,
) -> str:
    """Create a new agent from a ReproduceEvent, inheriting or freshly
    sampling each attribute per event.fresh_attributes. Returns the new
    agent's id."""
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
            sampled_array = _sample_distribution(attr, count=1, rng=rng)
            value = sampled_array[0]
            child_state[attr.name] = value.item() if hasattr(value, "item") else value
        else:
            child_state[attr.name] = parent.state.get(attr.name)

    child = AgentState(
        agent_id=str(uuid.uuid4()),
        agent_type_name=event.agent_type,
        state=child_state,
    )
    live_population[child.agent_id] = child
    return child.agent_id


def _apply_external_entry(
    event: ExternalEntryEvent,
    live_population: dict[str, AgentState],
    agent_types: dict[str, AgentType],
    rng: np.random.Generator,
) -> list[str]:
    """Add `count` freshly-sampled new agents of the given type. Returns
    the list of new agents' ids, in creation order."""
    if event.agent_type not in agent_types:
        raise KeyError(
            f"Cannot process external entry: agent_type '{event.agent_type}' "
            f"not found in agent_types."
        )

    agent_type_def = agent_types[event.agent_type]
    new_agent_ids: list[str] = []

    for _ in range(event.count):
        new_state: dict[str, Any] = {}
        for attr in agent_type_def.attributes:
            if attr.distribution is not None:
                sampled_array = _sample_distribution(attr, count=1, rng=rng)
                value = sampled_array[0]
                new_state[attr.name] = value.item() if hasattr(value, "item") else value
            else:
                new_state[attr.name] = None

        new_agent = AgentState(
            agent_id=str(uuid.uuid4()),
            agent_type_name=event.agent_type,
            state=new_state,
        )
        live_population[new_agent.agent_id] = new_agent
        new_agent_ids.append(new_agent.agent_id)

    return new_agent_ids