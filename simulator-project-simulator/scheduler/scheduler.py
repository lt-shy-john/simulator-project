"""
scheduler.py — Scheduling (S-06).

Scope:
  - compile_scheduling: parses the 'scheduling' section of config into a
    ScheduleConfig, once at simulation start.
  - resolve_step_agents: given the current population, returns the
    ordered list of agent IDs that should act this step, after applying
    quota (if any) and ordering (all_at_once / random / priority).

Design notes:
  - order and read_mode are INDEPENDENT settings — a researcher can
    combine any order with any read_mode.
      - order: all_at_once | random | priority
      - read_mode: frozen | live
    read_mode is threaded into executor.py's run_step (see executor.py) —
    this module only decides WHO acts and in WHAT ORDER.
  - Quota has two mutually exclusive modes (alternatives, not composable):
      - step_random_subset: stateless. Each step, sample `limit` agents
        at random from the given scope. No persistence across steps.
      - lifetime_budget: stateful. Each agent gets `limit` total actions
        across the WHOLE simulation run. Persists via
        agent.state["actions_remaining"] (inside the state dict, not a
        new top-level AgentState field, so it survives SoA round-trips).
  - UPDATED: quota.scope is now OPTIONAL. scope=<agent_type_name> means
    the quota applies only to agents of that type (other types are
    always eligible, unaffected by this quota). scope=None means the
    quota applies ACROSS THE WHOLE POPULATION regardless of type — e.g.
    "only 30 agents total may act this step, of any type" rather than
    "only 30 predators may act this step." This reflects the "per
    population" vs "per agent type" distinction from the original
    quota design conversation — previously scope was required, meaning
    only the per-type case was actually expressible.
  - Priority mode ties: agents with equal priority_attribute values are
    treated as equal — order between them is randomised, since no
    meaningful tiebreak exists by design.

Not in scope here:
  - Threading read_mode into NeighbourAccessor / executor.py's run_step
    (see executor.py — this integration is already done there).
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
    scope: str | None = None  # agent_type_name this quota applies to,
                               # or None for whole-population scope


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
                    scope: predator   # optional — omit for whole-population scope

    Returns:
        a compiled ScheduleConfig

    Raises:
        ValueError: if 'scheduling' section is missing, if order is
            invalid, if order is "priority" but priority_attribute is
            missing, if read_mode is invalid, or if quota.mode/limit is
            invalid. scope is optional — its absence is NOT an error.
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
        # scope is OPTIONAL — None (or absent) means whole-population scope.
        scope = quota_raw.get("scope")  # defaults to None if absent

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
    applying quota (if any).

    If quota.scope is set to an agent type name, only agents of that type
    are subject to the quota — all other types are always eligible. If
    quota.scope is None, the quota applies across the WHOLE population
    regardless of type (e.g. "30 agents total, any type, may act").

    step_random_subset: sample `limit` agents at random from the scoped
        pool, fresh every step. Stateless.

    lifetime_budget: filter the scoped pool to agents whose
        state["actions_remaining"] > 0 (or undefined, treated as
        unlimited). Does NOT decrement here — see consume_lifetime_action,
        called only after an agent's behaviour sequence has actually run.
    """
    if schedule.quota is None:
        return list(population.keys())

    quota = schedule.quota

    if quota.scope is None:
        # Whole-population scope — every agent is in the scoped pool,
        # nothing falls outside it.
        scoped_ids = list(population.keys())
        other_ids: list[str] = []
    else:
        scoped_ids = [
            aid for aid, agent in population.items()
            if agent.agent_type_name == quota.scope
        ]
        other_ids = [
            aid for aid, agent in population.items()
            if agent.agent_type_name != quota.scope
        ]

    if quota.mode == "step_random_subset":
        chosen = random.sample(scoped_ids, min(quota.limit, len(scoped_ids)))
        return other_ids + chosen

    else:  # lifetime_budget
        eligible = []
        for aid in scoped_ids:
            agent = population[aid]
            remaining = agent.state.get("actions_remaining")
            if remaining is None or remaining > 0:
                eligible.append(aid)
            # else: budget exhausted, not eligible
        return other_ids + eligible


def consume_lifetime_action(schedule: ScheduleConfig, agent: AgentState) -> None:
    """Decrement an agent's lifetime action budget, if applicable.

    Called by executor.py's run_step AFTER an agent's behaviour sequence
    has actually executed this step — not at selection time. No-op if
    quota isn't lifetime_budget, if the agent is outside the quota's
    scope (when scope is set to a specific type), or if the agent has no
    actions_remaining defined (unlimited).

    Args:
        schedule: the compiled ScheduleConfig
        agent: the agent that just finished acting this step
    """
    if schedule.quota is None or schedule.quota.mode != "lifetime_budget":
        return
    if schedule.quota.scope is not None and agent.agent_type_name != schedule.quota.scope:
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

    all_at_once: population insertion order (arbitrary but stable) —
        order doesn't semantically matter since reads are frozen.
    random: freshly shuffled every call.
    priority: sorted descending by schedule.priority_attribute. Ties are
        shuffled among themselves, not given a deterministic secondary
        sort.
    """
    eligible_ids = _apply_quota(schedule, population)

    if schedule.order == "all_at_once":
        return eligible_ids

    elif schedule.order == "random":
        shuffled = eligible_ids.copy()
        random.shuffle(shuffled)
        return shuffled

    else:  # priority
        by_priority: dict[float, list[str]] = {}
        for aid in eligible_ids:
            value = population[aid].state.get(schedule.priority_attribute, 0)
            by_priority.setdefault(value, []).append(aid)

        ordered: list[str] = []
        for value in sorted(by_priority.keys(), reverse=True):
            group = by_priority[value]
            random.shuffle(group)
            ordered.extend(group)

        return ordered