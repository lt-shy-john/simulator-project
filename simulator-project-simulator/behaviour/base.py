"""
base.py — BehaviourModule Protocol (S-05).

Scope:
  - BehaviourModule: structural interface all behaviour modules satisfy

Design notes:
  - Uses Protocol (not ABC), consistent with TopologyProtocol from S-03.
  - Each subclass defines its own __init__ — no shared constructor contract.
    A module like SIRInfection might take infection_rate/recovery_rate;
    a module like Treatment might take treatment_effectiveness. There's
    no meaningful shared constructor shape across arbitrary behaviours.
  - write_mode (deferred/immediate) is NOT declared on the module. It is
    entirely config-driven and owned by the executor — the module never
    knows or controls its own write mode. This keeps write_mode trustworthy:
    a module physically cannot bypass the mode because it never holds a
    raw mutable reference to a neighbour's state, only a NeighbourAccessor
    that has already been configured with the correct mode by the executor.
  - topology_name binding (which named topology this module draws
    neighbours from) is also NOT part of this interface — it's a config-level
    concern resolved by the executor before apply() is called. Required only
    when a module needs neighbours AND multiple topologies exist in config.

Not in scope here:
  - Concrete module implementations (SIRInfection, VaccineAdoption, etc.)
    live in separate topic-library folders, outside this ticket.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from runner.state import AgentState
from behaviour.accessor import NeighbourAccessor
from behaviour.model import Model


@runtime_checkable
class BehaviourModule(Protocol):
    """Structural interface for all behaviour modules.

    Any class implementing apply() satisfies this Protocol — no inheritance
    required. Each subclass defines its own __init__ for module-specific
    parameters (e.g. infection_rate, kill_probability).
    """

    def apply(
        self,
        agent: AgentState,
        neighbours: list[str],
        accessor: NeighbourAccessor,
        model: Model,
    ) -> None:
        """Apply this module's logic for a single agent, for one step.

        Called once per agent per step, in the order this module appears
        in the agent type's behaviour sequence (config-defined order).

        Within one agent's own sequence, this module's mutations to `agent`
        are immediately visible to later modules in the same sequence for
        the same agent (self-writes are always live, not deferred — see
        S-05 ticket notes). Mutations to neighbours go through `accessor`,
        whose read/write behaviour is determined by config (write_mode),
        not by this module.

        Args:
            agent: the AgentState for the agent currently being processed.
                   Mutating agent.state directly is always live — visible
                   to the next module in this agent's sequence immediately.
            neighbours: list of neighbour agent ID strings, resolved from
                        this module's bound topology (topology_name in
                        config). Empty list if this module doesn't use
                        neighbours (no topology_name set).
            accessor: NeighbourAccessor for reading/writing neighbour state.
                      Reads always return strict start-of-step (t-1) values.
                      Writes are applied immediately or deferred to step-end
                      depending on this module's configured write_mode —
                      the module has no visibility into which mode is active.
            model: the simulation-level context object (see model.py) —
                   gives access to step number, full population, global
                   parameters, shared RNG, and event logging. params, rng,
                   and log_event are backed by tickets not yet built
                   (S-11, S-10 respectively) — see model.py for details.
        """