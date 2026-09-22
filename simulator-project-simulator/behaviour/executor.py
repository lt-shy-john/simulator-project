"""
executor.py — Behaviour executor (S-05/S-06, updated for S-07 Agent Lifecycle).

Scope:
  - compile_behaviours: parses the 'behaviour' section of config ONCE at
    simulation start into ready-to-run CompiledEntry objects.
  - run_step: executes one simulation step.

Design notes (S-07 integration):
  - `model` is now expected to be a persistent SimulationModel (see
    model.py), built ONCE before the step loop starts — NOT rebuilt every
    call to run_step. This matters for run-scoped fields like model.rng,
    which must stay the same object across steps.
  - run_step calls model._reset_for_step(step_number, live_population) at
    the very start of each call — this updates step-scoped fields
    (model.step, model.agents, and clears model._pending_events) without
    touching run-scoped fields (model.rng, model.params).
  - agent_types (agent_type_name -> AgentType) is now a REQUIRED
    parameter — needed by apply_pending_lifecycle_events to look up
    AttributeDefinitions when reproduce/external_entry fresh-sample
    attributes.
  - At step-end, after all agents have been processed and deferred
    writes applied, apply_pending_lifecycle_events drains whatever
    model.reproduce()/remove()/external_entry() calls were queued during
    this step — same "process at step-end" pattern as deferred writes,
    per the ticket's own note about avoiding mid-step list mutation bugs.
  - step_number must be tracked by the CALLER (whatever runs the overall
    simulation loop, incrementing once per call to run_step) and passed
    in explicitly — run_step itself has no internal step counter.

Not in scope here:
  - The overall simulation loop that calls run_step repeatedly and
    increments step_number — that's runner/simulation.py's job, not
    covered here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union
import sys

from runner.soa import to_soa, ID_KEY
from topology.topology import TopologyProtocol
from behaviour.base import BehaviourModule
from behaviour.accessor import NeighbourAccessor, WriteMode, apply_deferred_writes
from behaviour.expressions import evaluate_expression
from behaviour.registry import get_behaviour
from scheduler.scheduler import ScheduleConfig, resolve_step_agents, consume_lifetime_action
from lifecycle.lifecycle import apply_pending_lifecycle_events
from stopping.engine import check_stopping, StopResult, StoppingConfig
from util.collector import collect_aggregates


# ---------------------------------------------------------------------------
# Compiled entry types
# ---------------------------------------------------------------------------

@dataclass
class CompiledModuleEntry:
    instance: BehaviourModule
    module_name: str
    params: dict[str, Any]
    topology_name: str | None
    write_mode: WriteMode


@dataclass
class CompiledExpressionEntry:
    expr: str
    topology_name: str | None


CompiledEntry = Union[CompiledModuleEntry, CompiledExpressionEntry]


# ---------------------------------------------------------------------------
# Compilation — done once at simulation start
# ---------------------------------------------------------------------------

def compile_behaviours(
    config: dict,
    topologies: dict[str, TopologyProtocol],
) -> dict[str, list[CompiledEntry]]:
    behaviour_config = config.get("behaviour", {})
    if not behaviour_config:
        raise ValueError(
            "Config must contain a 'behaviour' section with at least one "
            "agent type's behaviour sequence defined."
        )

    compiled: dict[str, list[CompiledEntry]] = {}

    for agent_type_name, entries in behaviour_config.items():
        compiled_entries: list[CompiledEntry] = []

        for entry in entries:
            topology_name = entry.get("topology_name")
            if topology_name is not None and topology_name not in topologies:
                raise ValueError(
                    f"Agent type '{agent_type_name}' behaviour entry references "
                    f"unknown topology '{topology_name}'. "
                    f"Known topologies: {sorted(topologies.keys())}"
                )

            if "module" in entry:
                module_name = entry["module"]
                module_cls = get_behaviour(module_name)
                params = entry.get("params", {})
                instance = module_cls(**params)

                write_mode = entry.get("write_mode", "deferred")
                if write_mode not in ("deferred", "immediate"):
                    raise ValueError(
                        f"Agent type '{agent_type_name}' module '{module_name}' has "
                        f"invalid write_mode '{write_mode}'. Expected 'deferred' or "
                        f"'immediate'."
                    )

                compiled_entries.append(CompiledModuleEntry(
                    instance=instance,
                    module_name=module_name,
                    params=params,
                    topology_name=topology_name,
                    write_mode=write_mode,
                ))

            elif "expression" in entry:
                compiled_entries.append(CompiledExpressionEntry(
                    expr=entry["expression"],
                    topology_name=topology_name,
                ))

            else:
                raise ValueError(
                    f"Agent type '{agent_type_name}' behaviour entry must contain "
                    f"either 'module' or 'expression'. Got: {entry}"
                )

        compiled[agent_type_name] = compiled_entries

    return compiled


# ---------------------------------------------------------------------------
# Neighbour cache — built once per step, before the per-agent loop
# ---------------------------------------------------------------------------

def _build_neighbour_cache(
    topologies: dict[str, TopologyProtocol],
    soa,
) -> dict[str, dict[str, list[str]]]:
    cache: dict[str, dict[str, list[str]]] = {}

    for topology_name, topology in topologies.items():
        cache[topology_name] = {}
        for arrays in soa.values():
            for agent_id in arrays[ID_KEY]:
                aid = str(agent_id)
                cache[topology_name][aid] = topology.get_neighbours(aid, soa)

    return cache


# ---------------------------------------------------------------------------
# Step execution
# ---------------------------------------------------------------------------

_DEFAULT_STOPPING_CONFIG = StoppingConfig(max_steps=sys.maxsize)

def run_step(
    live_population, compiled_behaviours, topologies, model, schedule,
    agent_types, step_number, aggregate_collectors=None, stopping_config=_DEFAULT_STOPPING_CONFIG,
) -> StopResult:
    model._reset_for_step(step_number, live_population)
    model.log_event("step_start", agent_id=None)

    frozen_population = {
        agent_id: agent.snapshot() for agent_id, agent in live_population.items()
    }
    soa = to_soa(list(frozen_population.values()))
    neighbour_cache = _build_neighbour_cache(topologies, soa)
    read_source = frozen_population if schedule.read_mode == "frozen" else live_population
    deferred_writes: list[tuple[str, str, Any]] = []
    ordered_agent_ids = resolve_step_agents(schedule, live_population, model.rng)

    for agent_id in ordered_agent_ids:
        agent = live_population[agent_id]
        entries = compiled_behaviours.get(agent.agent_type_name)
        if not entries:
            continue
        for entry in entries:
            neighbours = (
                neighbour_cache.get(entry.topology_name, {}).get(agent.agent_id, [])
                if entry.topology_name is not None else []
            )
            if isinstance(entry, CompiledModuleEntry):
                accessor = NeighbourAccessor(
                    read_source=read_source, live_population=live_population,
                    deferred_writes=deferred_writes, write_mode=entry.write_mode,
                )
                entry.instance.apply(agent, neighbours, accessor, model)
            else:
                neighbours_state = [read_source[nid].state for nid in neighbours]
                evaluate_expression(entry.expr, agent, neighbours_state)
        consume_lifetime_action(schedule, agent)

    apply_deferred_writes(live_population, deferred_writes)

    lifecycle_events = apply_pending_lifecycle_events(
        live_population, model._pending_events, agent_types, model.rng
    )
    for record in lifecycle_events:
        model.log_event(record["event_type"], agent_id=record["agent_id"], data=record["data"])

    # Aggregate collection - end of step, after lifecycle events, same
    # point stopping conditions are checked.
    row = collect_aggregates(model, aggregate_collectors or [])
    model._aggregate_log.append(row)

    model.log_event("step_end", agent_id=None)
    return check_stopping(model, stopping_config)