"""
executor.py — Behaviour executor (S-05, updated for S-06 scheduling).

Scope:
  - compile_behaviours: parses the 'behaviour' section of config ONCE at
    simulation start into ready-to-run CompiledEntry objects.
  - run_step: executes one simulation step. UPDATED (S-06) — agent
    processing order now comes from scheduling.resolve_step_agents()
    instead of a fixed by-agent-type-then-population-order iteration,
    and which population backs neighbour reads is chosen per
    schedule.read_mode rather than always the frozen snapshot.

Design notes (S-06 integration):
  - read_mode ("frozen" | "live") determines which population dict is
    passed as `read_source` to NeighbourAccessor, and which dict
    expressions build their `neighbours_state` list from. Both modules
    and expressions use the SAME read_source this step — read_mode is a
    single, step-wide setting, not something that can differ between a
    module and an expression in the same sequence (per researcher's
    explicit intent: "anything surrounding it should be the same").
      - "frozen": read_source = frozen_population (pre-step snapshot,
        the original S-05 behaviour — unchanged in effect)
      - "live": read_source = live_population (agents see same-step
        mutations from whoever was processed earlier in this step's
        order — enables cascades, order-dependent by design)
  - Agent processing order now comes from
    scheduling.resolve_step_agents(schedule, live_population), which
    already applies quota (if any) and order (all_at_once / random /
    priority). This REPLACES the old by-agent-type-then-population-order
    grouping — order now matters semantically whenever read_mode is
    "live" (it never mattered under "frozen", since nobody's reads
    could be affected by processing order in that mode).
  - consume_lifetime_action(schedule, agent) is called once per agent,
    AFTER that agent's full behaviour sequence has executed for this
    step — never before, and never inside resolve_step_agents itself
    (which only checks eligibility, doesn't mutate quota state). See
    scheduling.py for why this ordering matters.
  - Neighbour cache (topology resolution) is still built once per step
    from a frozen SoA snapshot, unchanged by S-06 — WHO your neighbours
    are stays fixed at step start regardless of read_mode; only the
    VALUES you read from them follow read_mode.

Not in scope here:
  - Trigger / All quota modes beyond step_random_subset / lifetime_budget
    (see scheduling.py) — these were the two settled for S-06.
  - Agent lifecycle (birth/death) triggered by behaviour — S-07.
  - model construction — run_step receives an already-built Model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Union

from runner.state import AgentState
from runner.soa import to_soa, ID_KEY
from topology.topology import TopologyProtocol
from behaviour.base import BehaviourModule
from behaviour.model import Model
from behaviour.accessor import NeighbourAccessor, WriteMode, apply_deferred_writes
from behaviour.expressions import evaluate_expression
from behaviour.registry import get_behaviour
from scheduler.scheduler import ScheduleConfig, resolve_step_agents, consume_lifetime_action


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
    neighbour state. Expressions can never write to neighbours, only read.
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

    Raises:
        ValueError: if the 'behaviour' section is missing or empty, if a
            behaviour entry has neither 'module' nor 'expression', if
            topology_name references an unknown topology, if write_mode
            is invalid, or if a module name is not registered
    """
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

    Unchanged by S-06 — neighbour IDENTITY is always resolved from the
    frozen pre-step SoA snapshot, regardless of read_mode. read_mode only
    affects what VALUES you see once you have a neighbour's ID, not
    whether they count as a neighbour this step.
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
    schedule: ScheduleConfig,
) -> None:
    """Execute one simulation step, mutating live_population in place.

    UPDATED (S-06): agent processing order comes from
    scheduling.resolve_step_agents (quota + order applied), and neighbour
    reads are sourced from either the frozen snapshot or the live
    population depending on schedule.read_mode. Self-writes remain always
    live regardless of read_mode (see base.py — this was never in question).

    Args:
        live_population: agent_id -> AgentState, the population being
            mutated this step
        compiled_behaviours: output of compile_behaviours — ready-to-run
            entries per agent type
        topologies: named topologies from build_topologies (S-03)
        model: simulation-level context object (see model.py)
        schedule: compiled ScheduleConfig from scheduling.compile_scheduling

    Notes:
        Agents whose type has no entry in compiled_behaviours are
        skipped (no behaviour configured for that type — not an error).
        Agents excluded by quota from resolve_step_agents simply don't
        appear in this step's processing at all.
    """
    # Frozen snapshot — always built, regardless of read_mode, since
    # neighbour cache / topology resolution still needs a stable,
    # pre-step view of who exists and what type they are.
    frozen_population: dict[str, AgentState] = {
        agent_id: agent.snapshot() for agent_id, agent in live_population.items()
    }

    soa = to_soa(list(frozen_population.values()))
    neighbour_cache = _build_neighbour_cache(topologies, soa)

    # Choose the read source for this step based on schedule.read_mode.
    # Both modules (via NeighbourAccessor) and expressions (via
    # neighbours_state) use this SAME source — read_mode is one setting
    # for the whole step, not something that can differ per entry type.
    read_source = frozen_population if schedule.read_mode == "frozen" else live_population

    deferred_writes: list[tuple[str, str, Any]] = []

    # Agent order now comes from scheduling — quota-filtered and ordered
    # per schedule.order (all_at_once / random / priority).
    ordered_agent_ids = resolve_step_agents(schedule, live_population)

    for agent_id in ordered_agent_ids:
        agent = live_population[agent_id]
        entries = compiled_behaviours.get(agent.agent_type_name)
        if not entries:
            continue  # no behaviour configured for this agent's type

        for entry in entries:
            neighbours = (
                neighbour_cache.get(entry.topology_name, {}).get(agent.agent_id, [])
                if entry.topology_name is not None
                else []
            )

            if isinstance(entry, CompiledModuleEntry):
                accessor = NeighbourAccessor(
                    read_source=read_source,
                    live_population=live_population,
                    deferred_writes=deferred_writes,
                    write_mode=entry.write_mode,
                )
                entry.instance.apply(agent, neighbours, accessor, model)

            else:  # CompiledExpressionEntry
                neighbours_state = [
                    read_source[nid].state for nid in neighbours
                ]
                evaluate_expression(entry.expr, agent, neighbours_state)

        # Lifetime quota is only spent once the agent has actually
        # finished acting this step — never before (see scheduling.py).
        consume_lifetime_action(schedule, agent)

    # Apply all deferred neighbour writes once every agent has been processed.
    apply_deferred_writes(live_population, deferred_writes)