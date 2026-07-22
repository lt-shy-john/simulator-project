"""
accessor.py — NeighbourAccessor (S-05).

Scope:
  - NeighbourAccessor: the only way a behaviour module can read or write
    another agent's state. Modules never hold a raw mutable reference to
    a neighbour's AgentState — this is what makes write_mode enforceable
    rather than merely a convention module authors have to remember.

Design notes:
  - Reads always come from the frozen, start-of-step population snapshot
    (strict t-1). This is independent of write_mode — read behaviour never
    varies. A module always sees neighbours as they were before this step
    began, never a neighbour's in-progress mutations from earlier in the
    same step's agent-processing order.
  - Writes depend on write_mode, set by the executor from config — the
    module itself has no write_mode parameter and cannot control this:
      - "immediate": write lands directly in the live population, visible
        to that neighbour's own module sequence if/when it runs later in
        this same step (or, if already run, does nothing until next step's
        read, since that agent's sequence already executed against its
        own snapshot for this step).
      - "deferred": write is queued and only applied when the step ends,
        via apply_deferred_writes(). No agent sees the effect of a deferred
        write until the following step.
  - Self-writes (agent mutating agent.state directly, not through this
    accessor) are always live by design — see base.py. This accessor is
    only for neighbour access.

Not in scope here:
  - Atomic/paired writes (e.g. simultaneous game-theory payoff crediting
    for both participants in one operation) — current design only supports
    single-key, single-target writes. Worth revisiting if paired-write
    correctness issues surface once game theory / stock market style
    modules are built.
"""

from __future__ import annotations

from typing import Any, Literal

from runner.state import AgentState


WriteMode = Literal["deferred", "immediate"]


class NeighbourAccessor:
    """Controlled read/write channel to neighbour state for one module's
    apply() call.

    A new NeighbourAccessor is constructed by the executor for each
    module invocation, configured with that module's write_mode from
    config. Modules interact with neighbours exclusively through this
    object — never through a raw AgentState reference.
    """

    def __init__(
        self,
        frozen_population: dict[str, AgentState],
        live_population: dict[str, AgentState],
        deferred_writes: list[tuple[str, str, Any]],
        write_mode: WriteMode,
    ):
        """
        Args:
            frozen_population: agent_id -> AgentState, captured at the
                start of this step, before any agent has been processed.
                Read-only. All reads go through this, regardless of
                write_mode.
            live_population: agent_id -> AgentState, the population
                currently being mutated this step (each agent's own
                in-progress snapshot from S-02). Used for immediate writes.
            deferred_writes: shared list that this accessor appends to
                when write_mode is "deferred". The executor drains this
                at step-end via apply_deferred_writes().
            write_mode: "deferred" or "immediate" — determines how write()
                behaves. Set by the executor from this module's config
                entry, not by the module itself.
        """
        self._frozen_population = frozen_population
        self._live_population = live_population
        self._deferred_writes = deferred_writes
        self._write_mode = write_mode

    def read(self, neighbour_id: str, key: str) -> Any:
        """Read an attribute from a neighbour's start-of-step (t-1) state.

        Always reads from the frozen population snapshot, regardless of
        write_mode — read behaviour is constant across all modules.

        Args:
            neighbour_id: the neighbour's agent ID
            key: the attribute name to read

        Returns:
            the attribute value as of the start of this step

        Raises:
            KeyError: if neighbour_id is not in the frozen population,
                or if key is not a defined attribute for that agent
        """
        if neighbour_id not in self._frozen_population:
            raise KeyError(
                f"neighbour_id '{neighbour_id}' not found in frozen population."
            )
        return self._frozen_population[neighbour_id].get(key)

    def write(self, neighbour_id: str, key: str, value: Any) -> None:
        """Write an attribute to a neighbour's state.

        Behaviour depends on write_mode, set by the executor from config:
          - "immediate": applied directly to live_population now.
          - "deferred": queued, applied only at step-end.

        Args:
            neighbour_id: the neighbour's agent ID
            key: the attribute name to write
            value: the new value

        Raises:
            KeyError: if neighbour_id is not in the live population
                (immediate mode only — deferred writes are validated
                when applied at step-end, not when queued)
        """
        if self._write_mode == "immediate":
            if neighbour_id not in self._live_population:
                raise KeyError(
                    f"neighbour_id '{neighbour_id}' not found in live population."
                )
            self._live_population[neighbour_id].set(key, value)
        else:  # deferred
            self._deferred_writes.append((neighbour_id, key, value))


def apply_deferred_writes(
    live_population: dict[str, AgentState],
    deferred_writes: list[tuple[str, str, Any]],
) -> None:
    """Apply all queued deferred writes to the live population at step-end.

    Called once by the executor after all agents' behaviour sequences
    have run for this step, before the population is swapped back as
    the new live state (S-02's apply_snapshot_updates).

    Writes are applied in the order they were queued. If multiple deferred
    writes target the same (neighbour_id, key) pair, the last one queued
    wins — no conflict detection or merging is performed.

    Args:
        live_population: agent_id -> AgentState, mutated in place
        deferred_writes: the queue populated by NeighbourAccessor.write()
            calls during this step

    Raises:
        KeyError: if a queued neighbour_id is not found in live_population
            at apply time (e.g. the agent was removed mid-step)
    """
    for neighbour_id, key, value in deferred_writes:
        if neighbour_id not in live_population:
            raise KeyError(
                f"Cannot apply deferred write: neighbour_id '{neighbour_id}' "
                f"not found in live population (may have been removed this step)."
            )
        live_population[neighbour_id].set(key, value)