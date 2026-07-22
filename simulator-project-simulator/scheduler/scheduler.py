"""
scheduling.py — Scheduling (S-06).

Scope:
  - compile_scheduling: parses the 'scheduling' section of config into a
    ScheduleConfig, once at simulation start (same pattern as
    compile_behaviours in S-05).
  - resolve_step_agents: given the current population, returns the
    ordered list of agent IDs that should act this step, after applying
    quota (if any) and ordering (all_at_once / random / priority).

Design notes:
  - order and read_mode are INDEPENDENT settings, not coupled to a single
    scheduling "mode" — a researcher can combine any order with any
    read_mode. This mirrors the two-axis structure from earlier scheduling
    discussion (order of actions vs whether actions see live/frozen state),
    just applied at the population level rather than within one agent's
    own behaviour sequence.
      - order: all_at_once | random | priority
      - read_mode: frozen | live
    read_mode does NOT get resolved here — this module only decides WHO
    acts and in WHAT ORDER. Actually wiring read_mode into
    NeighbourAccessor's read() behaviour is executor.py's responsibility
    (see notes at the bottom of this file — NOT YET IMPLEMENTED, since it
    requires changing accessor.py's hardcoded frozen-only read guarantee
    from S-05).
  - Quota has two mutually exclusive modes (alternatives, not composable):
      - step_random_subset: stateless. Each step, sample `limit` agents
        at random from the given scope (agent type). No persistence
        needed across steps.
      - lifetime_budget: stateful. Each agent gets `limit` total actions
        across the WHOLE simulation run, not per step. Requires a
        persistent counter — stored as agent.state["actions_remaining"],
        NOT a new top-level AgentState field, so it survives SoA
        round-trips (to_soa/from_soa only convert `state` dict contents
        plus __ids__ — a new top-level field like mutation_count would
        silently be dropped on conversion, same gap mutation_count
        already has).
  - Priority mode ties: agents with equal priority_attribute values are
    treated as equal — order between them is randomised, since no
    meaningful tiebreak exists by design (researcher's own words: "let
    it be a random shuffle, others don't necessarily have a meaning").

Not in scope here:
  - Threading read_mode into NeighbourAccessor / executor.py's run_step —
    flagged as follow-up work, not yet implemented.
  - Step count / seed logging — depends on S-10/S-11, placeholder only.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

from runner.state import AgentState


OrderMode = Literal["all_at_once", "random", "priority"]
ReadMode = Literal["frozen", "live"]
QuotaMode = Literal["step_random_subset", "lifetime_budget"]


@dataclass
class QuotaConfig:
    mode: QuotaMode
    limit: int
    scope: str  # agent_type_name this quota applies to


@dataclass
class ScheduleConfig:
    order: OrderMode
    read_mode: ReadMode
    priority_attribute: str | None = None  # required if order == "priority"
    quota: QuotaConfig | None = None  # None means no quota — everyone acts


# ---------------------------------------------------------------------------
# Compilation — done once at simulation start
# ---------------------------------------------------------------------------

def compile_scheduling(config: dict) -> ScheduleConfig:
    """Parse the 'scheduling' section of config into a ScheduleConfig.

    Args:
        config: the full simulation config dict, containing a 'scheduling'
            section, e.g.
                scheduling:
                  order: priority
                  read_mode: live
                  priority_attribute: wealth
                  quota:
                    mode: step_random_subset
                    limit: 30
                    scope: predator

    Returns:
        a compiled ScheduleConfig

    Raises:
        ValueError: if 'scheduling' section is missing, if order is
            invalid, if order is "priority" but priority_attribute is
            missing, if read_mode is invalid, or if quota.mode is invalid
    """
    scheduling_config = config.get("scheduling")
    if not scheduling_config:
        raise ValueError(
            "Config must contain a 'scheduling' section."
        )

    order = scheduling_config.get("order")
    if order not in ("all_at_once", "random", "priority"):
        raise ValueError(
            f"Invalid scheduling order '{order}'. Expected one of: "
            f"'all_at_once', 'random', 'priority'."
        )

    read_mode = scheduling_config.get("read_mode")
    if read_mode not in ("frozen", "live"):
        raise ValueError(
            f"Invalid scheduling read_mode '{read_mode}'. Expected one of: "
            f"'frozen', 'live'."
        )

    priority_attribute = scheduling_config.get("priority_attribute")
    if order == "priority" and not priority_attribute:
        raise ValueError(
            "scheduling.order is 'priority' but no priority_attribute was "
            "given."
        )

    quota_raw = scheduling_config.get("quota")
    quota = None
    if quota_raw is not None:
        quota_mode = quota_raw.get("mode")
        if quota_mode not in ("step_random_subset", "lifetime_budget"):
            raise ValueError(
                f"Invalid quota mode '{quota_mode}'. Expected one of: "
                f"'step_random_subset', 'lifetime_budget'."
            )
        limit = quota_raw.get("limit")
        if not isinstance(limit, int) or limit < 1:
            raise ValueError(
                f"quota.limit must be a positive integer, got {limit}."
            )
        scope = quota_raw.get("scope")
        if not scope:
            raise ValueError("quota.scope (agent type name) is required.")

        quota = QuotaConfig(mode=quota_mode, limit=limit, scope=scope)

    return ScheduleConfig(
        order=order,
        read_mode=read_mode,
        priority_attribute=priority_attribute,
        quota=quota,
    )


# ---------------------------------------------------------------------------
# Quota resolution
# ---------------------------------------------------------------------------

def _apply_quota(
    schedule: ScheduleConfig,
    population: dict[str, AgentState],
) -> list[str]:
    """Return the list of agent IDs eligible to act this step, after
    applying quota (if any). Agents not in the quota's scope (agent type)
    are always eligible — quota only restricts agents of the named type.

    step_random_subset: sample `limit` agents at random from the scope
        type, fresh every step. Stateless.

    lifetime_budget: filter to agents of the scope type whose
        state["actions_remaining"] > 0. Agents without "actions_remaining"
        defined (e.g. a type never given this attribute) are treated as
        unlimited — always eligible. Persistent across steps via the
        state dict, survives SoA round-trips.

        IMPORTANT: this function only checks eligibility — it does NOT
        decrement actions_remaining. The decrement happens in
        executor.py's run_step, AFTER an agent's behaviour sequence has
        actually executed (see consume_lifetime_action below), not at
        selection time. This matters if a future ticket (e.g. Lifecycle,
        S-07) introduces a reason an agent could be selected this step
        but then skipped before actually running (e.g. dies mid-step) —
        in that case the lifetime action should NOT be spent, since the
        agent never really got to act.
    """
    if schedule.quota is None:
        return list(population.keys())

    quota = schedule.quota
    scope_ids = [
        aid for aid, agent in population.items()
        if agent.agent_type_name == quota.scope
    ]
    other_ids = [
        aid for aid, agent in population.items()
        if agent.agent_type_name != quota.scope
    ]

    if quota.mode == "step_random_subset":
        chosen = random.sample(scope_ids, min(quota.limit, len(scope_ids)))
        return other_ids + chosen

    else:  # lifetime_budget
        eligible = []
        for aid in scope_ids:
            agent = population[aid]
            remaining = agent.state.get("actions_remaining")
            if remaining is None or remaining > 0:
                eligible.append(aid)
            # else: budget exhausted, not eligible — permanently skipped
            # for the rest of the run unless something else replenishes it
        return other_ids + eligible


def consume_lifetime_action(schedule: ScheduleConfig, agent: AgentState) -> None:
    """Decrement an agent's lifetime action budget, if applicable.

    Called by executor.py's run_step AFTER an agent's behaviour sequence
    has actually executed this step — not at selection time. No-op if
    quota isn't lifetime_budget, if the agent isn't in the quota's scope,
    or if the agent has no actions_remaining defined (unlimited).

    Args:
        schedule: the compiled ScheduleConfig
        agent: the agent that just finished acting this step
    """
    if schedule.quota is None or schedule.quota.mode != "lifetime_budget":
        return
    if agent.agent_type_name != schedule.quota.scope:
        return
    remaining = agent.state.get("actions_remaining")
    if remaining is not None:
        agent.set("actions_remaining", remaining - 1)


# ---------------------------------------------------------------------------
# Order resolution
# ---------------------------------------------------------------------------

def resolve_step_agents(
    schedule: ScheduleConfig,
    population: dict[str, AgentState],
) -> list[str]:
    """Return the ordered list of agent IDs that should act this step,
    after applying quota and ordering.

    all_at_once: order doesn't semantically matter (everyone reads frozen
        state regardless of processing order), but a list is still
        returned for the executor to iterate — population insertion
        order is used, arbitrary but stable.
    random: freshly shuffled every call.
    priority: sorted descending by schedule.priority_attribute. Ties are
        NOT given a deterministic secondary sort — equal-priority agents
        are shuffled among themselves, since no meaningful tiebreak
        exists by design.

    Args:
        schedule: the compiled ScheduleConfig
        population: agent_id -> AgentState, current population

    Returns:
        ordered list of agent IDs eligible to act this step
    """
    eligible_ids = _apply_quota(schedule, population)

    if schedule.order == "all_at_once":
        return eligible_ids

    elif schedule.order == "random":
        shuffled = eligible_ids.copy()
        random.shuffle(shuffled)
        return shuffled

    else:  # priority
        # Group by priority value first, so ties can be shuffled within
        # their own group rather than relying on sort stability (which
        # would silently preserve population insertion order for ties —
        # not a real tiebreak, just an accident of implementation).
        by_priority: dict[float, list[str]] = {}
        for aid in eligible_ids:
            value = population[aid].state.get(schedule.priority_attribute, 0)
            by_priority.setdefault(value, []).append(aid)

        ordered: list[str] = []
        for value in sorted(by_priority.keys(), reverse=True):
            group = by_priority[value]
            random.shuffle(group)  # ties treated as equal, shuffled
            ordered.extend(group)

        return ordered


# ---------------------------------------------------------------------------
# NOT YET IMPLEMENTED — follow-up work required in executor.py:
#
# read_mode is compiled here but not yet threaded into run_step /
# NeighbourAccessor. Currently, accessor.py's read() ALWAYS reads from
# frozen_population regardless of any setting — this was a hard S-05
# guarantee. Supporting read_mode == "live" means run_step needs to pass
# a different population dict as the "read source" to NeighbourAccessor
# depending on schedule.read_mode:
#   - "frozen": read source = frozen_population (current S-05 behaviour)
#   - "live": read source = live_population (agents see same-step
#     mutations from whoever was processed earlier in this step's order)
#
# This also means run_step's agent iteration needs to use
# resolve_step_agents()'s ordered list instead of its current
# by-agent-type-then-population-order iteration, since order now matters
# semantically for "live" read_mode (it never mattered for "frozen").
#
# Additionally: run_step must call consume_lifetime_action(schedule, agent)
# once per agent, AFTER that agent's full behaviour sequence has executed
# for this step — not before. This is what actually spends a lifetime
# quota action; resolve_step_agents/_apply_quota only checks eligibility,
# it never mutates actions_remaining itself (see consume_lifetime_action
# docstring for why this ordering matters).
# ---------------------------------------------------------------------------