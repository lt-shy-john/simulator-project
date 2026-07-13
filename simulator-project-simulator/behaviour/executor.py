"""
executor.py — Behaviour executor (S-05).

Scope:
  - compile_behaviours: parses the 'behaviour' section of config ONCE at
    simulation start into ready-to-run CompiledEntry objects (module
    instances already constructed, expressions kept as strings). Avoids
    re-parsing config or re-instantiating modules on every step.
  - run_step: executes one simulation step — for every agent, in
    agent-type-then-behaviour-sequence order, runs its compiled entries.
    Mutates the live population in place.

Design notes:
  - Topology resolution happens ONCE per step, before the per-agent loop,
    via _build_neighbour_cache. Each topology's get_neighbours() is called
    once per agent and the result is cached as a list (not a true
    iterator — a real iterator would be exhausted after one pass if a
    module loops over neighbours more than once, silently returning
    nothing on a second pass. A list has no such risk).
  - frozen_population (strict t-1 reads) is built once per step as a
    snapshot of live_population BEFORE any agent is processed. This is
    distinct from live_population, which is actively mutated as the step
    runs — frozen_population must never change during the step, or the
    t-1 read guarantee (accessor.py, expressions.py) breaks.
  - Self-writes (a module mutating `agent.state` directly, or an
    expression mutating its own agent's state) are always live — visible
    to the next entry in that same agent's sequence immediately. This
    is what "agent-type-then-behaviour-sequence order" with a single
    threaded AgentState per agent naturally gives you, no extra work
    needed — see base.py notes.
  - Neighbour-affecting writes (via NeighbourAccessor, module entries
    only — expressions cannot write to neighbours, see expressions.py)
    follow each module's configured write_mode: "immediate" applies to
    live_population right away; "deferred" queues into a shared list,
    applied once via apply_deferred_writes() after all agents have been
    processed for this step.

Not in scope here:
  - Trigger / Quota / All update modes — separate tickets, layered on
    top of this sequential-execution mechanism.
  - Agent lifecycle (birth/death) triggered by behaviour — S-07.
  - model construction — run_step receives an already-built Model,
    doesn't build one itself (see model.py; concrete Model construction
    depends on S-10/S-11).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Union

from runner.state import AgentState
from runner.soa import to_soa, ID_KEY
from topology.topology import TopologyProtocol
from behaviour.base import BehaviourModule
from behaviour.model import Model
from behaviour.accessor import NeighbourAccessor, WriteMode, apply_deferred_writes
from behaviour.expressions import evaluate_expression
from behaviour.registry import get_behaviour


# ---------------------------------------------------------------------------
# Compiled entry types
# ---------------------------------------------------------------------------

@dataclass
class CompiledModuleEntry:
    """A behaviour config entry compiled into a ready-to-run module instance."""
    instance: BehaviourModule
    topology_name: str | None
    write_mode: WriteMode


@dataclass
class CompiledExpressionEntry:
    """A behaviour config entry compiled from an expression string.

    topology_name is optional — only needed if the expression reads
    neighbour state (e.g. 'state["x"] = any(n["y"] for n in neighbours)').
    Expressions can never write to neighbours, only read (see expressions.py).
    """
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
    """Parse the 'behaviour' section of config into ready-to-run entries.

    Called once at simulation start, not per step — module instances are
    constructed here and reused for every subsequent call to run_step.

    Args:
        config: the full simulation config dict, containing a 'behaviour'
            section keyed by agent type name, e.g.
                behaviour:
                  person:
                    - module: SIRInfection
                      topology_name: contact
                      write_mode: deferred
                      params:
                        infection_rate: 0.05
                    - expression: 'state["age"] += 1'
        topologies: the topologies dict from build_topologies (S-03),
            used to validate topology_name references

    Returns:
        dict mapping agent_type_name to an ordered list of CompiledEntry,
        preserving config order (Python dicts preserve insertion order)

    Raises:
        ValueError: if a behaviour entry has neither 'module' nor
            'expression', if topology_name references an unknown
            topology, if write_mode is invalid, or if a module name
            is not registered
    """
    behaviour_config = config.get("behaviour", {})
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
                module_cls = get_behaviour(module_name)  # raises KeyError if unknown
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
    """Resolve every agent's neighbours for every topology, once per step.

    Returns:
        dict mapping topology_name -> agent_id -> list of neighbour IDs.
        Lists, not iterators — see module docstring for why.
    """
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

def run_step(
    live_population: dict[str, AgentState],
    compiled_behaviours: dict[str, list[CompiledEntry]],
    topologies: dict[str, TopologyProtocol],
    model: Model,
) -> None:
    """Execute one simulation step, mutating live_population in place.

    For every agent, in agent-type-then-behaviour-sequence order, runs
    that agent type's compiled entries against the agent. Self-writes
    are always live (visible to the next entry in the same agent's
    sequence). Neighbour writes follow each module's write_mode.

    Args:
        live_population: agent_id -> AgentState, the population being
            mutated this step (S-02 snapshots, about to become the new
            live state once this step completes)
        compiled_behaviours: output of compile_behaviours — ready-to-run
            entries per agent type
        topologies: named topologies from build_topologies (S-03)
        model: simulation-level context object (see model.py)

    Notes:
        Agent types present in live_population but absent from
        compiled_behaviours are simply not processed (no behaviour
        configured for that type — not an error). Agent types in
        compiled_behaviours with no matching agents in the population
        are similarly a no-op.
    """
    # Frozen snapshot — strict t-1, never mutated during this step.
    frozen_population: dict[str, AgentState] = {
        agent_id: agent.snapshot() for agent_id, agent in live_population.items()
    }

    # Topology resolution happens once, before any agent is processed,
    # using the frozen (pre-step) population as the source of truth for
    # who exists and what type they are.
    soa = to_soa(list(frozen_population.values()))
    neighbour_cache = _build_neighbour_cache(topologies, soa)

    deferred_writes: list[tuple[str, str, Any]] = []

    # Group live agents by type for agent-type-then-sequence iteration.
    by_type: dict[str, list[AgentState]] = {}
    for agent in live_population.values():
        by_type.setdefault(agent.agent_type_name, []).append(agent)

    for agent_type_name, entries in compiled_behaviours.items():
        for agent in by_type.get(agent_type_name, []):
            for entry in entries:
                neighbours = (
                    neighbour_cache.get(entry.topology_name, {}).get(agent.agent_id, [])
                    if entry.topology_name is not None
                    else []
                )

                if isinstance(entry, CompiledModuleEntry):
                    accessor = NeighbourAccessor(
                        frozen_population=frozen_population,
                        live_population=live_population,
                        deferred_writes=deferred_writes,
                        write_mode=entry.write_mode,
                    )
                    entry.instance.apply(agent, neighbours, accessor, model)

                else:  # CompiledExpressionEntry
                    neighbours_state = [
                        frozen_population[nid].state for nid in neighbours
                    ]
                    evaluate_expression(entry.expr, agent, neighbours_state)

    # Apply all deferred neighbour writes once every agent has been processed.
    apply_deferred_writes(live_population, deferred_writes)