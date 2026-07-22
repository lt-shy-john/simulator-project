"""
accessor.py — NeighbourAccessor (S-05, updated for S-06 scheduling).

Scope:
  - NeighbourAccessor: the only way a behaviour module can read or write
    another agent's state. Modules never hold a raw mutable reference to
    a neighbour's AgentState — this is what makes write_mode enforceable
    rather than merely a convention module authors have to remember.

Design notes:
  - UPDATED (S-06): reads no longer come unconditionally from a strict
    t-1 snapshot. Which population dict backs reads is now determined by
    executor.py based on schedule.read_mode ("frozen" or "live") — see
    scheduling.py. This constructor parameter is named `read_source`
    (previously `frozen_population`) to reflect that it's whichever
    population the executor decided reads should come from this step,
    not always the pre-step snapshot. Under read_mode == "frozen", the
    executor passes the pre-step snapshot here (old S-05 behaviour,
    unchanged in effect). Under read_mode == "live", the executor passes
    the live, currently-being-mutated population instead, allowing
    same-step cascades (an agent processed later in this step's order
    can see an earlier agent's mutations from this same step).
  - Writes still depend on write_mode, set by the executor from config —
    this is unchanged by S-06 and independent of read_mode:
      - "immediate": write lands directly in the live population.
      - "deferred": write is queued and only applied when the step ends,
        via apply_deferred_writes().
  - Self-writes (agent mutating agent.state directly, not through this
    accessor) are always live by design — see base.py. This accessor is
    only for neighbour access.

Not in scope here:
  - Atomic/paired writes (e.g. simultaneous game-theory payoff crediting) —
    current design only supports single-key, single-target writes.
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
    config, and with a read_source chosen according to schedule.read_mode
    (see scheduling.py). Modules interact with neighbours exclusively
    through this object — never through a raw AgentState reference.
    """

    def __init__(
        self,
        read_source: dict[str, AgentState],
        live_population: dict[str, AgentState],
        deferred_writes: list[tuple[str, str, Any]],
        write_mode: WriteMode,
    ):
        """
        Args:
            read_source: agent_id -> AgentState that all read() calls draw
                from this step. Chosen by the executor based on
                schedule.read_mode — the pre-step frozen snapshot under
                "frozen" mode, or the live population under "live" mode.
                This accessor has no opinion on which one it's given.
            live_population: agent_id -> AgentState, the population
                currently being mutated this step. Used for immediate
                writes, regardless of read_mode.
            deferred_writes: shared list that this accessor appends to
                when write_mode is "deferred". The executor drains this
                at step-end via apply_deferred_writes().
            write_mode: "deferred" or "immediate" — determines how write()
                behaves. Set by the executor from this module's config
                entry, not by the module itself. Independent of read_mode.
        """
        self._read_source = read_source
        self._live_population = live_population
        self._deferred_writes = deferred_writes
        self._write_mode = write_mode

    def read(self, neighbour_id: str, key: str) -> Any:
        """Read an attribute from a neighbour's state, via read_source.

        Which population read_source points to (frozen pre-step snapshot,
        or live current-step state) is decided by the executor based on
        schedule.read_mode — this method itself is agnostic to which.

        Args:
            neighbour_id: the neighbour's agent ID
            key: the attribute name to read

        Returns:
            the attribute value, as of whatever read_source represents

        Raises:
            KeyError: if neighbour_id is not in read_source, or if key
                is not a defined attribute for that agent
        """
        if neighbour_id not in self._read_source:
            raise KeyError(
                f"neighbour_id '{neighbour_id}' not found in read source."
            )
        return self._read_source[neighbour_id].get(key)

    def write(self, neighbour_id: str, key: str, value: Any) -> None:
        """Write an attribute to a neighbour's state.

        Behaviour depends on write_mode, set by the executor from config
        (independent of read_mode):
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